import { ApiError } from '../api/http.ts';
import { PageCursorExpiredError } from '../catalog/pagedResource.ts';
import type {
    OwnLandingPage,
    OwnLandingCard,
    PartnerLanding,
    PartnerLandingCreatePayload,
    PartnerLandingUpdatePayload,
} from './types.ts';

export type LandingDraft = Omit<PartnerLandingCreatePayload, 'status'>;
type Transport = {
    list: (cursor: string | null, signal: AbortSignal) => Promise<OwnLandingPage>;
    load: (id: number, signal: AbortSignal) => Promise<PartnerLanding>;
    create: (draft: PartnerLandingCreatePayload, signal: AbortSignal) => Promise<PartnerLanding>;
    update: (
        id: number,
        value: PartnerLandingUpdatePayload,
        signal: AbortSignal,
    ) => Promise<PartnerLanding>;
};
type State = {
    account: string | null;
    items: OwnLandingCard[];
    nextCursor: string | null;
    loaded: boolean;
    record: PartnerLanding | null;
    draft: LandingDraft;
    editing: boolean;
    status: 'ready' | 'loading' | 'saving' | 'publishing';
    error: unknown;
    conflict: boolean;
    saved: boolean;
};
const draftOf = (value: PartnerLanding | null): LandingDraft => ({
    slug: value?.slug ?? '',
    title: value?.title ?? '',
    eyebrow: value?.eyebrow ?? '',
    headline: value?.headline ?? '',
    description: value?.description ?? '',
    cta_label: value?.cta_label ?? 'Выбрать модель',
    cta_href: value?.cta_href ?? '/',
    image_url: value?.image_url ?? '',
    template_key: 'light-running',
    content: value ? structuredClone(value.content) : { faq: [] },
    product_ids: value ? [...value.product_ids] : [],
});
export const landingCard = (record: PartnerLanding): OwnLandingCard => ({
    id: record.id, version: record.version, slug: record.slug, title: record.title,
    image_url: record.image_url ?? null, status: record.status, product_count: record.product_ids.length,
});
const empty = (account: string | null): State => ({
    account,
    items: [],
    nextCursor: null,
    loaded: false,
    record: null,
    draft: draftOf(null),
    editing: false,
    status: 'ready',
    error: null,
    conflict: false,
    saved: false,
});
export const landingDirty = (state: Pick<State, 'draft' | 'record'>) =>
    JSON.stringify(state.draft) !== JSON.stringify(draftOf(state.record));

/** One editor per account lifetime; only confirmed server responses advance versions. */
export class LandingEditor {
    private state = empty(null);
    private listeners = new Set<() => void>();
    private transport: Transport | null = null;
    private operation: AbortController | null = null;
    private generation = 0;
    getSnapshot = () => this.state;
    subscribe = (listener: () => void) => {
        this.listeners.add(listener);
        return () => {
            this.listeners.delete(listener);
        };
    };
    private emit(patch: Partial<State>) {
        this.state = { ...this.state, ...patch };
        this.listeners.forEach((listener) => listener());
    }
    dispose = () => {
        this.generation++;
        this.operation?.abort();
        this.operation = null;
        this.transport = null;
    };
    setAccount = (account: string | null, transport: Transport | null) => {
        this.dispose();
        this.transport = account ? transport : null;
        this.state = empty(account);
        this.emit({});
        return this.transport ? this.loadList() : Promise.resolve(false);
    };
    private async perform(
        status: State['status'],
        action: (transport: Transport, signal: AbortSignal) => Promise<Partial<State>>,
    ) {
        const transport = this.transport;
        if (!transport || this.operation) return false;
        const generation = this.generation,
            controller = new AbortController();
        this.operation = controller;
        this.emit({ status, error: null, saved: false });
        try {
            const patch = await action(transport, controller.signal);
            if (controller.signal.aborted || generation !== this.generation) return false;
            this.emit({ ...patch, status: 'ready' });
            return true;
        } catch (error) {
            if (controller.signal.aborted || generation !== this.generation) return false;
            this.emit({
                status: 'ready',
                error,
                conflict:
                    this.state.conflict || (error instanceof ApiError && error.status === 409),
            });
            return false;
        } finally {
            if (this.operation === controller) this.operation = null;
        }
    }
    loadList = () =>
        this.perform('loading', async (t, s) => {
            const page = await t.list(null, s);
            return { items: page.items, nextCursor: page.next_cursor, loaded: true };
        });
    more = () =>
        this.state.nextCursor && !(this.state.error instanceof PageCursorExpiredError)
            ? this.perform('loading', async (t, s) => {
                  const page = await t.list(this.state.nextCursor, s),
                      ids = new Set(this.state.items.map((item) => item.id));
                  return {
                      items: [
                          ...this.state.items,
                          ...page.items.filter((item) => !ids.has(item.id)),
                      ],
                      nextCursor: page.next_cursor,
                  };
              })
            : Promise.resolve(false);
    createDraft = () => {
        if (this.transport && !this.operation)
            this.emit({
                record: null,
                draft: draftOf(null),
                editing: true,
                error: null,
                conflict: false,
                saved: false,
            });
    };
    close = () => {
        if (!this.operation)
            this.emit({ editing: false, error: null, conflict: false, saved: false });
    };
    open = (id: number) =>
        this.perform('loading', async (t, s) => {
            const record = await t.load(id, s);
            return { record, draft: draftOf(record), editing: true, conflict: false };
        });
    reload = () => (this.state.record ? this.open(this.state.record.id) : this.loadList());
    setField = <Key extends keyof LandingDraft>(key: Key, value: LandingDraft[Key]) => {
        if (this.transport && !this.operation && this.state.editing)
            this.emit({
                draft: { ...this.state.draft, [key]: value },
                saved: false,
                ...(!this.state.record && key === 'slug' ? { conflict: false, error: null } : {}),
            });
    };
    setProducts = (values: number[]) => {
        const ids = [...new Set(values)];
        if (ids.length > 50 || ids.some((id) => !Number.isSafeInteger(id) || id <= 0)) return;
        this.setField('product_ids', ids);
    };
    private confirmed(record: PartnerLanding, resetDraft: boolean): Partial<State> {
        const card = landingCard(record);
        const items = this.state.items.some((item) => item.id === record.id)
            ? this.state.items.map((item) => (item.id === record.id ? card : item))
            : [card, ...this.state.items];
        return {
            record,
            items,
            draft: resetDraft ? draftOf(record) : this.state.draft,
            editing: true,
            conflict: false,
            saved: true,
        };
    }
    save = () => {
        if (!this.state.editing || this.state.conflict) return Promise.resolve(false);
        const record = this.state.record,
            draft = structuredClone(this.state.draft);
        return this.perform('saving', async (t, s) => {
            const { slug, ...fields } = draft;
            const saved = record
                ? await t.update(record.id, { ...fields, expected_version: record.version }, s)
                : await t.create({ ...fields, slug, status: 'draft' }, s);
            return this.confirmed(saved, true);
        });
    };
    publish = (published: boolean) => {
        const record = this.state.record;
        if (
            !record ||
            this.state.conflict ||
            (published && (landingDirty(this.state) || !record.product_ids.length))
        )
            return Promise.resolve(false);
        return this.perform('publishing', async (t, s) =>
            this.confirmed(
                await t.update(
                    record.id,
                    { expected_version: record.version, status: published ? 'published' : 'draft' },
                    s,
                ),
                published,
            ),
        );
    };
}
