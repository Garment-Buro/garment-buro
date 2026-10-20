import { ApiError } from '../api/http.ts';
import type { OwnPublicProfile, PublicProfileWrite } from '../catalog/people.ts';

type Draft = Pick<PublicProfileWrite, 'slug' | 'display_name' | 'bio'>;
type Status = 'ready' | 'loading' | 'saving' | 'publishing' | 'uploading' | 'removing';
export type PublicProfileTransport = {
    load: (signal: AbortSignal) => Promise<OwnPublicProfile | null>;
    save: (value: PublicProfileWrite, signal: AbortSignal) => Promise<OwnPublicProfile>;
    upload: (version: number, file: Blob, signal: AbortSignal) => Promise<OwnPublicProfile>;
    remove: (version: number, signal: AbortSignal) => Promise<OwnPublicProfile>;
    preview: (id: number, signal: AbortSignal) => Promise<Blob>;
};
type EditorState = {
    account: string | null;
    profile: OwnPublicProfile | null;
    draft: Draft;
    loaded: boolean;
    status: Status;
    conflict: boolean;
    error: unknown | null;
    saved: boolean;
    avatarUrl: string | null;
    avatarError: boolean;
};
const draftOf = (profile: OwnPublicProfile | null): Draft => ({
    slug: profile?.slug ?? '', display_name: profile?.display_name ?? '', bio: profile?.bio ?? '',
});
const empty = (account: string | null): EditorState => ({
    account, profile: null, draft: draftOf(null), loaded: false, status: 'ready',
    error: null, conflict: false, saved: false, avatarUrl: null, avatarError: false,
});
export function hasPublicProfileChanges(state: Pick<EditorState, 'draft' | 'profile'>) {
    const saved = draftOf(state.profile);
    return state.draft.slug !== saved.slug || state.draft.display_name !== saved.display_name || state.draft.bio !== saved.bio;
}

/** One in-memory public form per account lifetime; the server owns all versions. */
export class PublicProfileEditor {
    private snapshot = empty(null);
    private listeners = new Set<() => void>();
    private transport: PublicProfileTransport | null = null;
    private operation: AbortController | null = null;
    private preview: AbortController | null = null;
    private generation = 0;
    private urls: { create: (value: Blob) => string; revoke: (value: string) => void };

    constructor(urls = { create: (blob: Blob) => URL.createObjectURL(blob), revoke: (url: string) => URL.revokeObjectURL(url) }) {
        this.urls = urls;
    }
    getSnapshot = () => this.snapshot;
    subscribe = (listener: () => void) => {
        this.listeners.add(listener);
        return () => { this.listeners.delete(listener); };
    };
    private publish(value: EditorState) {
        this.snapshot = value;
        this.listeners.forEach(listener => listener());
    }
    setAccount = (account: string | null, transport: PublicProfileTransport | null) => {
        this.dispose();
        this.transport = account ? transport : null;
        this.publish(empty(account));
        return this.transport ? this.reload() : Promise.resolve(false);
    };
    setField = (field: keyof Draft, value: string) => {
        if (!this.transport || this.operation || !this.snapshot.loaded) return;
        this.publish({ ...this.snapshot, draft: { ...this.snapshot.draft, [field]: value }, saved: false });
    };
    private clearPreview() {
        this.preview?.abort();
        this.preview = null;
        if (this.snapshot.avatarUrl) this.urls.revoke(this.snapshot.avatarUrl);
    }
    private async loadPreview(id: number | null, transport: PublicProfileTransport) {
        this.clearPreview();
        this.publish({ ...this.snapshot, avatarUrl: null, avatarError: false });
        if (id === null) return;
        const generation = this.generation;
        const controller = new AbortController();
        this.preview = controller;
        try {
            const blob = await transport.preview(id, controller.signal);
            if (controller.signal.aborted || generation !== this.generation) return;
            this.publish({ ...this.snapshot, avatarUrl: this.urls.create(blob) });
        } catch {
            if (!controller.signal.aborted && generation === this.generation) this.publish({ ...this.snapshot, avatarError: true });
        } finally {
            if (this.preview === controller) this.preview = null;
        }
    }
    private async perform(status: Status, action: (transport: PublicProfileTransport, signal: AbortSignal) => Promise<OwnPublicProfile | null>, resetDraft = false) {
        const transport = this.transport;
        if (!transport || this.operation || (status !== 'loading' && (!this.snapshot.loaded || this.snapshot.conflict))) return false;
        const generation = this.generation;
        const controller = new AbortController();
        this.operation = controller;
        this.publish({ ...this.snapshot, status, error: null, saved: false });
        try {
            const profile = await action(transport, controller.signal);
            if (controller.signal.aborted || generation !== this.generation) return false;
            const previousAvatar = this.snapshot.profile?.avatar_id ?? null;
            this.publish({ ...this.snapshot, profile, draft: resetDraft ? draftOf(profile) : this.snapshot.draft,
                status: 'ready', loaded: true, conflict: false, error: null, saved: status !== 'loading' });
            if (status === 'loading' || previousAvatar !== (profile?.avatar_id ?? null)) void this.loadPreview(profile?.avatar_id ?? null, transport);
            return true;
        } catch (error) {
            if (controller.signal.aborted || generation !== this.generation) return false;
            this.publish({ ...this.snapshot, status: 'ready', error, conflict: this.snapshot.conflict || error instanceof ApiError && error.status === 409 });
            return false;
        } finally {
            if (this.operation === controller) this.operation = null;
        }
    }
    reload = () => this.perform('loading', (transport, signal) => transport.load(signal), true);
    save = () => {
        const value: PublicProfileWrite = { ...this.snapshot.draft, version: this.snapshot.profile?.version ?? 0, is_published: this.snapshot.profile?.is_published ?? false };
        return this.perform('saving', (transport, signal) => transport.save(value, signal), true);
    };
    setPublished = (published: boolean) => {
        const profile = this.snapshot.profile;
        if (!profile || published && hasPublicProfileChanges(this.snapshot)) return Promise.resolve(false);
        return this.perform('publishing', (transport, signal) => transport.save({ ...draftOf(profile), version: profile.version, is_published: published }, signal), published);
    };
    upload = (file: Blob) => {
        const profile = this.snapshot.profile;
        return profile ? this.perform('uploading', (transport, signal) => transport.upload(profile.version, file, signal)) : Promise.resolve(false);
    };
    removeAvatar = () => {
        const profile = this.snapshot.profile;
        return profile ? this.perform('removing', (transport, signal) => transport.remove(profile.version, signal)) : Promise.resolve(false);
    };
    dispose = () => {
        this.generation++;
        this.operation?.abort();
        this.operation = null;
        this.transport = null;
        this.clearPreview();
    };
}
