export interface FavoriteTransport {
    status: (ids: number[], signal: AbortSignal) => Promise<number[]>;
    save: (id: number, wanted: boolean, signal: AbortSignal) => Promise<void>;
}

export interface FavoriteState {
    account: string | null;
    ids: number[];
    knownIds: number[];
    pendingIds: number[];
    error: unknown | null;
}

export const emptyFavoriteState: FavoriteState = {
    account:null, ids:[], knownIds:[], pendingIds:[], error:null,
};

/** Confirmed account data only. Authentication and HTTP remain outside this controller. */
export class FavoriteController {
    private snapshot: FavoriteState = emptyFavoriteState;
    private listeners = new Set<() => void>();
    private requests = new Set<AbortController>();
    private known = new Set<number>();
    private saved = new Set<number>();
    private pending = new Set<number>();
    private reading = new Set<number>();
    private transport: FavoriteTransport | null = null;
    private generation = 0;

    getSnapshot = () => this.snapshot;
    subscribe = (listener: () => void) => {
        this.listeners.add(listener);
        return () => {this.listeners.delete(listener)};
    };
    private publish(error: unknown | null = null) {
        this.snapshot = {...this.snapshot, ids:[...this.saved], knownIds:[...this.known], pendingIds:[...this.pending], error};
        this.listeners.forEach(listener => listener());
    }

    setAccount(account: string | null, transport: FavoriteTransport | null) {
        this.transport = transport;
        if(this.snapshot.account === account) return;
        this.generation++;
        this.requests.forEach(request => request.abort());
        this.requests.clear();
        this.known.clear(); this.saved.clear(); this.pending.clear(); this.reading.clear();
        this.snapshot = {...emptyFavoriteState, account};
        this.publish();
    }

    async ensureStatus(productIds: readonly number[]) {
        const transport = this.transport;
        if(!transport || !this.snapshot.account) return;
        const generation = this.generation;
        const unknown = [...new Set(productIds)].filter(id => !this.known.has(id) && !this.reading.has(id));
        for(let offset=0; offset<unknown.length; offset+=100) {
            if(generation !== this.generation) return;
            const ids = unknown.slice(offset, offset+100).filter(id => !this.known.has(id) && !this.reading.has(id));
            if(!ids.length) continue;
            const controller = new AbortController();
            this.requests.add(controller);
            ids.forEach(id => this.reading.add(id));
            try {
                const saved = new Set(await transport.status(ids, controller.signal));
                if(controller.signal.aborted || generation !== this.generation) return;
                ids.forEach(id => {
                    this.known.add(id);
                    if(saved.has(id)) this.saved.add(id);
                    else this.saved.delete(id);
                });
                this.publish();
            } catch(error) {
                if(controller.signal.aborted || generation !== this.generation) return;
                this.publish(error);
                return;
            } finally {
                this.requests.delete(controller);
                if(generation === this.generation) ids.forEach(id => this.reading.delete(id));
            }
        }
    }

    async refreshStatus(productIds: readonly number[]) {
        const ids = productIds.filter(id => !this.pending.has(id) && !this.reading.has(id));
        ids.forEach(id => this.known.delete(id));
        this.publish();
        await this.ensureStatus(ids);
    }

    toggle = async (id: number): Promise<boolean> => {
        const transport = this.transport;
        if(!transport || !this.snapshot.account || !this.known.has(id) || this.pending.has(id)) return false;
        const wanted = !this.saved.has(id), generation = this.generation;
        const controller = new AbortController();
        this.requests.add(controller);
        this.pending.add(id);
        this.publish();
        let error: unknown | null = null;
        try {
            await transport.save(id, wanted, controller.signal);
            if(controller.signal.aborted || generation !== this.generation) return false;
            if(wanted) this.saved.add(id);
            else this.saved.delete(id);
            return true;
        } catch(failure) {
            error = failure;
            return false;
        } finally {
            this.requests.delete(controller);
            if(generation === this.generation && !controller.signal.aborted) {
                this.pending.delete(id);
                this.publish(error);
            }
        }
    };

    dispose = () => this.setAccount(null, null);
}
