/** Public files are described once; product and SKU images refer to their IDs. */
export interface ConstructorImage {
    media_id: number;
    role: string;
    sort_order: number;
}

export interface ConstructorProduct {
    schema_version: 1;
    id: number;
    title: string;
    price: number;
    stock_quantity: number;
    sizes: string[];
    media_assets: Array<{ id: number; url: string; content_type: 'image/jpeg' | 'image/png' | 'image/webp' }>;
    images: ConstructorImage[];
    variants: Array<{
        id: number;
        size: string | null;
        color: string | null;
        color_hex: string | null;
        stock_quantity: number;
        width_cm: number | null;
        height_cm: number | null;
        images: ConstructorImage[];
    }>;
}

const record = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const id = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) > 0 && Number(value) <= 2147483647;
const nonnegative = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value >= 0;
const stock = (value: unknown) => nonnegative(value) && Number.isSafeInteger(value);
const nullableText = (value: unknown) => value === null || typeof value === 'string';
const dimension = (value: unknown) => value === null || nonnegative(value);
const imageUrl = (value: unknown) => typeof value === 'string' && !/[\u0000-\u0020\\]/.test(value)
    && (value.startsWith('/') && !value.startsWith('//') || /^https?:\/\//.test(value));

/** A mismatched deployment or incomplete response must never supply a usable model. */
export function readConstructorProduct(value: unknown, expectedId: number): ConstructorProduct {
    const invalid = () => { throw new Error('Не удалось получить полный состав модели. Обновите страницу и попробуйте ещё раз.'); };
    if (!record(value) || value.schema_version !== 1 || !id(value.id) || value.id !== expectedId
        || typeof value.title !== 'string' || !nonnegative(value.price) || !stock(value.stock_quantity)
        || !Array.isArray(value.sizes) || !value.sizes.every(size => typeof size === 'string')
        || !Array.isArray(value.media_assets) || !Array.isArray(value.variants)) return invalid();
    const assets = new Set<number>();
    for (const asset of value.media_assets) {
        if (!record(asset) || !id(asset.id) || assets.has(asset.id) || !imageUrl(asset.url)
            || !['image/jpeg', 'image/png', 'image/webp'].includes(String(asset.content_type))) return invalid();
        assets.add(asset.id);
    }
    const images = (links: unknown) => Array.isArray(links) && links.every(link => record(link)
        && id(link.media_id) && assets.has(link.media_id) && typeof link.role === 'string'
        && stock(link.sort_order));
    if (!images(value.images)) return invalid();
    const variants = new Set<number>();
    for (const variant of value.variants) {
        if (!record(variant) || !id(variant.id) || variants.has(variant.id)
            || !nullableText(variant.size) || !nullableText(variant.color) || !nullableText(variant.color_hex)
            || !stock(variant.stock_quantity) || !dimension(variant.width_cm) || !dimension(variant.height_cm)
            || !images(variant.images)) return invalid();
        variants.add(variant.id);
    }
    return value as unknown as ConstructorProduct;
}

export function constructorImageUrls(product: ConstructorProduct | null, links: readonly ConstructorImage[] | undefined, role: string): string[] {
    const assets = new Map((product?.media_assets ?? []).map(asset => [asset.id, asset.url]));
    return [...new Set((links ?? []).filter(link => link.role === role)
        .toSorted((a, b) => a.sort_order - b.sort_order)
        .flatMap(link => assets.has(link.media_id) ? [assets.get(link.media_id)!] : []))];
}
