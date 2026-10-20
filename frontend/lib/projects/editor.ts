import type { ConstructorDraftState } from '../constructor/types.ts';
import { createProjectImageResolver } from './images.ts';
import { restoreProjectSnapshot, serializeProjectSnapshot } from './snapshot.ts';
import type { ImageReference, ProjectCreate, ProjectDetail, ProjectImage, ProjectImages, ProjectKind, ProjectUpdate } from './types.ts';

export type ProjectTransport = {
    create: (payload: ProjectCreate, signal: AbortSignal) => Promise<ProjectDetail>;
    update: (id: number, payload: ProjectUpdate, signal: AbortSignal) => Promise<ProjectDetail>;
    get: (id: number, signal: AbortSignal) => Promise<ProjectDetail>;
    images: (id: number, version: number, signal: AbortSignal) => Promise<ProjectImages>;
    upload: (image: Blob, signal?: AbortSignal) => Promise<ProjectImage>;
};
type SaveInput = {
    productId: number;
    title: string;
    kind: ProjectKind;
    draft: ConstructorDraftState;
    assets: ReadonlyArray<{ id: number; url: string }>;
};
type EditorState = {
    account: string | null;
    document: ProjectDetail | null;
    restored: ConstructorDraftState | null;
    status: 'idle' | 'loading' | 'saving';
    error: unknown | null;
};
const signature = (input: SaveInput) => JSON.stringify({ productId: input.productId, title: input.title, kind: input.kind, draft: input.draft });

/** Owns one account's project operation, retained image IDs and uncertain POST. */
export class ProjectEditor {
    private snapshot: EditorState = { account: null, document: null, restored: null, status: 'idle', error: null };
    private listeners = new Set<() => void>();
    private controller: AbortController | null = null;
    private transport: ProjectTransport | null = null;
    private references = new Map<string, ImageReference>();
    private privateMediaIds = new Set<number>();
    private targetId: number | null = null;
    private pendingCreate: { payload: ProjectCreate; signature: string } | null = null;
    private origin: string;

    constructor(options: { origin: string }) { this.origin = options.origin; }
    getSnapshot = () => this.snapshot;
    subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
    getImageSources = () => ({
        publicImages: new Set([...this.references].filter(([, reference]) => !this.privateMediaIds.has(reference.mediaId)).map(([source]) => source)),
        privateImages: new Map([...this.references].filter(([, reference]) => this.privateMediaIds.has(reference.mediaId)).map(([source, reference]) => [source, reference.mediaId])),
    });
    private publish(value: EditorState) { this.snapshot = value; this.listeners.forEach(listener => listener()); }
    setAccount = (account: string | null, transport: ProjectTransport | null) => {
        this.dispose();
        this.transport = transport;
        this.publish({ account, document: null, restored: null, status: 'idle', error: null });
    };
    private async perform<Result>(status: 'loading' | 'saving', operation: (transport: ProjectTransport, signal: AbortSignal) => Promise<Result>): Promise<Result | null> {
        if (!this.transport || this.controller || !this.snapshot.account) return null;
        const transport = this.transport, controller = new AbortController();
        this.controller = controller;
        this.publish({ ...this.snapshot, status, error: null });
        try {
            const result = await operation(transport, controller.signal);
            controller.signal.throwIfAborted();
            return result;
        } catch (error) {
            if (!controller.signal.aborted) {
                // Validation rejects the write before commit. Network/5xx
                // outcomes retain the original POST for idempotent recovery.
                if (status === 'saving' && error && typeof error === 'object' && 'status' in error && error.status === 422) this.pendingCreate = null;
                this.publish({ ...this.snapshot, error });
            }
            return null;
        } finally {
            if (this.controller === controller) {
                this.controller = null;
                this.publish({ ...this.snapshot, status: 'idle' });
            }
        }
    }
    load = async (id: number) => {
        if (this.controller) return false;
        this.targetId = id;
        if (this.snapshot.document?.id !== id) {
            this.publish({ ...this.snapshot, document: null, restored: null });
        }
        return Boolean(await this.perform('loading', async (transport, signal) => {
            const document = await transport.get(id, signal);
            signal.throwIfAborted();
            const images = await transport.images(id, document.version, signal);
            signal.throwIfAborted();
            if (images.version !== document.version) throw new Error('Версия проекта изменилась. Повторите загрузку.');
            const restored = restoreProjectSnapshot(document.snapshot, images.items);
            this.references = new Map(images.items.map(image => [image.url, { mediaId: image.id }]));
            this.privateMediaIds = new Set(images.items.filter(image => typeof image.expires_in === 'number').map(image => image.id));
            this.pendingCreate = null;
            this.publish({ ...this.snapshot, document, restored });
            return true;
        }));
    };
    reload = (id: number | null = this.targetId) => id === null ? Promise.resolve(false) : this.load(id);
    save = async (input: SaveInput) => this.perform('saving', async (transport, signal) => {
        if (this.targetId !== null && !this.snapshot.document) throw new Error('Сначала загрузите сохранённый проект.');
        const wantedSignature = signature(input);
        let payload: ProjectCreate | ProjectUpdate;
        let savedSignature = wantedSignature;
        if (this.pendingCreate) {
            payload = this.pendingCreate.payload;
            savedSignature = this.pendingCreate.signature;
        } else {
            for (const asset of input.assets) this.references.set(asset.url, { mediaId: asset.id });
            const snapshot = await serializeProjectSnapshot(input.draft, createProjectImageResolver({
                origin: this.origin, references: this.references, upload: async (blob, uploadSignal) => {
                    const media = await transport.upload(blob, uploadSignal);
                    uploadSignal?.throwIfAborted();
                    this.privateMediaIds.add(media.id);
                    return media;
                },
            }), signal);
            signal.throwIfAborted();
            const fields = { title: input.title, kind: input.kind, snapshot };
            payload = this.snapshot.document
                ? { ...fields, expected_version: this.snapshot.document.version }
                : { ...fields, product_id: input.productId, client_key: crypto.randomUUID() };
            if ('client_key' in payload) this.pendingCreate = { payload, signature: wantedSignature };
        }
        const document = 'client_key' in payload
            ? await transport.create(payload, signal)
            : await transport.update(this.snapshot.document!.id, payload, signal);
        signal.throwIfAborted();
        this.targetId = document.id;
        this.pendingCreate = null;
        this.publish({ ...this.snapshot, document });
        return { document, matchesDraft: savedSignature === wantedSignature };
    });
    dispose = () => {
        this.controller?.abort();
        this.controller = null;
        this.transport = null;
        this.references = new Map();
        this.privateMediaIds = new Set();
        this.pendingCreate = null;
        this.targetId = null;
    };
}
