import { DESIGN_IMAGE_MAX_BYTES, isDesignImageUrl, type DesignImage, type ImportedDesignImage } from '../api/designMedia.ts';
import { readLocalRasterImage } from '../api/http.ts';
import type { CartItem } from '../cart/types.ts';
import type { ConstructorProduct } from './product.ts';

type Payload = Omit<CartItem, 'id'>;
type Sources = { publicImages: ReadonlySet<string>; privateImages: ReadonlyMap<string, number> };
type Dependencies = {
    origin: string;
    getScope: () => string | null;
    upload: (blob: Blob, signal: AbortSignal) => Promise<DesignImage>;
    import: (ids: number[], signal: AbortSignal) => Promise<ImportedDesignImage[]>;
    now?: () => number;
};

/** Public URLs must come from this product, never from untrusted draft JSON. */
export function constructorPublicImages(product: ConstructorProduct): Set<string> {
    return new Set((product.media_assets ?? []).map(image => image.url));
}

/** One editor operation: preserve input, retain successful uploads for retry, commit once. */
export class ConstructorCartPreparation {
    private readonly deps: Dependencies;
    private readonly listeners = new Set<() => void>();
    private active: AbortController | null = null;
    private cache = new Map<string, DesignImage>();
    private scope: string | null = null;
    constructor(deps: Dependencies) { this.deps = deps; }
    getSnapshot = () => this.active !== null;
    subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
    private publish() { this.listeners.forEach(listener => listener()); }
    cancel = () => { this.active?.abort(); this.active = null; this.publish(); };
    reset = () => { this.cancel(); this.cache.clear(); this.scope = null; };

    async submit(payload: Payload, sources: Sources, commit: (payload: Payload) => void): Promise<boolean> {
        if (this.active) return false;
        const scope = this.deps.getScope();
        if (scope === null) throw new Error('Дождитесь восстановления сессии и попробуйте ещё раз.');
        if (this.scope !== scope) { this.cache.clear(); this.scope = scope; }
        const controller = new AbortController(), signal = controller.signal;
        this.active = controller; this.publish();
        const timer = setTimeout(() => controller.abort(new DOMException('Не удалось сохранить изображения вовремя. Попробуйте ещё раз.', 'TimeoutError')), 120_000);
        const check = () => {
            signal.throwIfAborted();
            if (this.deps.getScope() !== scope) throw new DOMException('Account changed', 'AbortError');
        };
        try {
            const copy = structuredClone(payload), customization = copy.customization;
            if (!customization) throw new Error('Дизайн недоступен. Откройте товар заново.');
            const wanted = new Set([copy.image, customization.modelImages.front, customization.modelImages.back,
                ...customization.decorations.map(item => item.image)]);
            if (wanted.size > 103) throw new Error('В дизайне слишком много изображений.');
            const now = (this.deps.now || Date.now)();
            for (const [source, image] of this.cache) {
                if (!wanted.has(source) || Date.parse(image.expires_at) <= now + 60_000) this.cache.delete(source);
            }
            const urls = new Map<string, string>();
            const local: string[] = [], imports = new Map<number, string[]>();
            for (const source of wanted) {
                // Resolve trusted identities before looking at data URLs. A saved
                // local image can already have a private project media ID.
                const privateId = sources.privateImages.get(source);
                if (isDesignImageUrl(source)) urls.set(source, source);
                else if (this.cache.has(source)) urls.set(source, this.cache.get(source)!.url);
                else if (privateId !== undefined) imports.set(privateId, [...(imports.get(privateId) || []), source]);
                else if (sources.publicImages.has(source) && !/^(data:|blob:)/i.test(source)) urls.set(source, source);
                else if (/^data:image\/(png|jpeg|webp);base64,/i.test(source) || source.startsWith(`blob:${this.deps.origin}/`)) local.push(source);
                else throw new Error('Изображение не связано с товаром или проектом. Загрузите свой файл заново.');
            }
            check();
            if (imports.size) {
                const images = await this.deps.import([...imports.keys()], signal);
                check();
                if (images.length !== imports.size || new Set(images.map(image => image.media_id)).size !== imports.size
                    || images.some(image => !imports.has(image.media_id) || !isDesignImageUrl(image.url))) throw new Error('Не удалось сохранить все изображения проекта.');
                for (const image of images) for (const source of imports.get(image.media_id)!) {
                    this.cache.set(source, image); urls.set(source, image.url);
                }
            }
            for (const source of local) {
                check();
                const blob = await readLocalRasterImage(source, { origin: this.deps.origin, maxBytes: DESIGN_IMAGE_MAX_BYTES, signal });
                check();
                const image = await this.deps.upload(blob, signal);
                check();
                if (!isDesignImageUrl(image.url)) throw new Error('Не удалось сохранить изображение.');
                this.cache.set(source, image); urls.set(source, image.url);
            }
            const url = (source: string) => {
                const value = urls.get(source);
                if (!value) throw new Error('Не удалось сохранить изображение.');
                return value;
            };
            copy.image = url(copy.image);
            customization.modelImages = { front: url(customization.modelImages.front), back: url(customization.modelImages.back) };
            customization.decorations = customization.decorations.map(item => ({ ...item, image: url(item.image) }));
            if (new TextEncoder().encode(JSON.stringify(customization)).length > 64 * 1024) throw new Error('В дизайне слишком много данных. Уменьшите число элементов и попробуйте ещё раз.');
            check();
            commit(copy);
            return true;
        } finally {
            clearTimeout(timer);
            if (this.active === controller) { this.active = null; this.publish(); }
        }
    }
}
