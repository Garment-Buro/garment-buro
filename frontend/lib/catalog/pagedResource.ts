export interface ResourcePage<Item, Cursor> {
    items: Item[];
    next_cursor: Cursor | null;
}

export type ResourceInitial<Item, Cursor> = {key: string} & (
    {page: ResourcePage<Item, Cursor>} | {error: string}
);

export interface PagedState<Item, Cursor> {
    key: string;
    status: 'idle' | 'loading' | 'ready' | 'error';
    items: Item[];
    nextCursor: Cursor | null;
    loadingMore: boolean;
    error: unknown | null;
}

type LoadPage<Item, Cursor> = (cursor: Cursor | null, signal: AbortSignal) => Promise<ResourcePage<Item, Cursor>>;

export class PageCursorExpiredError extends Error {
    constructor() {
        super('Список изменился. Обновите его, чтобы продолжить.');
        this.name = 'PageCursorExpiredError';
    }
}

/** One mounted view owns one resource; no global cache or persisted customer data. */
export class PagedResource<Item extends {id: number | string}, Cursor = string> {
    private snapshot: PagedState<Item, Cursor> = {
        key:'', status:'idle', items:[], nextCursor:null, loadingMore:false, error:null,
    };
    private listeners = new Set<() => void>();
    private controller: AbortController | null = null;
    private generation = 0;
    private loader: LoadPage<Item, Cursor> | null = null;

    constructor(initial?: ResourceInitial<Item, Cursor>) {
        if(initial) this.snapshot = 'page' in initial
            ? {key:initial.key, status:'ready', items:initial.page.items, nextCursor:initial.page.next_cursor, loadingMore:false, error:null}
            : {key:initial.key, status:'error', items:[], nextCursor:null, loadingMore:false, error:initial.error};
    }

    getSnapshot = () => this.snapshot;
    subscribe = (listener: () => void) => {
        this.listeners.add(listener);
        return () => {this.listeners.delete(listener)};
    };

    private publish(value: PagedState<Item, Cursor>) {
        this.snapshot = value;
        this.listeners.forEach(listener => listener());
    }

    start = async (key: string, loader: LoadPage<Item, Cursor>, options: {reuseSettled?: boolean} = {}) => {
        this.dispose();
        this.loader = loader;
        // Public storefront hydration/reconnection can retain its own snapshot.
        // Private consumers and explicit reload keep the default fresh request.
        if(options.reuseSettled && this.snapshot.key === key && ['ready', 'error'].includes(this.snapshot.status)) {
            if(this.snapshot.loadingMore) this.publish({...this.snapshot, loadingMore:false});
            return;
        }
        this.publish({key, status:'loading', items:[], nextCursor:null, loadingMore:false, error:null});
        await this.fetchPage(false);
    };

    private async fetchPage(append: boolean) {
        if(!this.loader) return;
        const generation = this.generation;
        const controller = new AbortController();
        this.controller = controller;
        if(append) this.publish({...this.snapshot, loadingMore:true, error:null});
        try {
            const page = await this.loader(append ? this.snapshot.nextCursor : null, controller.signal);
            if(controller.signal.aborted || generation !== this.generation) return;
            const items = new Map((append ? this.snapshot.items : []).map(item => [item.id, item]));
            page.items.forEach(item => items.set(item.id, item));
            this.publish({...this.snapshot, status:'ready', items:[...items.values()], nextCursor:page.next_cursor, loadingMore:false, error:null});
        } catch(error) {
            if(controller.signal.aborted || generation !== this.generation) return;
            this.publish({...this.snapshot, status:append ? 'ready' : 'error', loadingMore:false, error});
        } finally {
            if(this.controller === controller) this.controller = null;
        }
    }

    loadMore = async () => {
        if(this.snapshot.status !== 'ready' || this.controller || this.snapshot.nextCursor === null
            || this.snapshot.error instanceof PageCursorExpiredError) return;
        await this.fetchPage(true);
    };

    reload = async () => {
        if(this.loader) await this.start(this.snapshot.key, this.loader);
    };

    dispose = () => {
        this.generation++;
        this.controller?.abort();
        this.controller = null;
        this.loader = null;
    };
}
