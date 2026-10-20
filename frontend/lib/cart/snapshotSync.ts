import type {CartItem, CartServerPayload, CartServerUpdate} from './types.ts';
import {normalizeCartItems} from './utils/cart.ts';

export class CartRevisionConflictError extends Error {
    constructor() {super('Cart changed since it was read'); this.name = 'CartRevisionConflictError'}
}

export interface CartSyncState {
    items: CartItem[];
    baseRevision: string | null;
    baseKnown: boolean;
    cartDirty: boolean;
    pendingWrite: CartServerUpdate | null;
    cartSyncConflict: boolean;
}

interface CartSnapshotIO {
    local: () => CartSyncState & {cartId: string};
    read: (cartId: string) => Promise<CartServerPayload>;
    write: (cartId: string, update: CartServerUpdate) => Promise<CartServerPayload>;
    patch: (update: Partial<CartSyncState>) => void;
    operationId: () => string;
    initialized: () => void;
    failed: () => void;
    succeeded: () => void;
}

// Object key order and omitted/null customization must not create false edits.
const canonical = (value: unknown): unknown => {
    if(Array.isArray(value)) return value.map(canonical);
    if(value && typeof value === 'object') return Object.fromEntries(
        Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, entry]) => [key, canonical(entry)]),
    );
    return value;
};
const sameItems = (a: CartItem[], b: CartItem[]) => JSON.stringify(canonical(normalizeCartItems(a))) === JSON.stringify(canonical(normalizeCartItems(b)));

/** One in-flight write per document; the API revision arbitrates other documents. */
export class CartSnapshotSync {
    private tail: Promise<void> = Promise.resolve();
    private initialization: Promise<void> | null = null;
    private saving: Promise<void> | null = null;
    private ready = false;
    private readonly io: CartSnapshotIO;

    constructor(io: CartSnapshotIO) {this.io = io}

    private enqueue(job: () => Promise<void>) {
        const running = this.tail.then(async () => {
            try {await job()} catch(error) {
                if(error instanceof CartRevisionConflictError) this.io.patch({cartSyncConflict: true});
                else this.io.failed();
            }
        });
        this.tail = running;
        return running;
    }

    private accept(remote: CartServerPayload) {
        this.io.patch({items: normalizeCartItems(remote.items), baseRevision: remote.revision,
            baseKnown: true, cartDirty: false, pendingWrite: null, cartSyncConflict: false});
        this.io.succeeded();
    }

    private async transmit() {
        const before = this.io.local();
        const pending = before.pendingWrite;
        if(!pending) return;
        const remote = await this.io.write(before.cartId, pending);
        const current = this.io.local();
        if(current.cartId !== before.cartId || current.pendingWrite?.operation_id !== pending.operation_id) return;
        const dirty = !sameItems(current.items, pending.items);
        this.io.patch({baseRevision: remote.revision, baseKnown: true, pendingWrite: null,
            cartDirty: dirty, cartSyncConflict: false,
            ...(!dirty ? {items: normalizeCartItems(remote.items)} : {})});
        this.io.succeeded();
    }

    private async run() {
        if(this.io.local().cartSyncConflict) return;
        // Replay the identical persisted request before reading/rebasing anything.
        if(this.io.local().pendingWrite) await this.transmit();
        if(!this.ready) {
            const before = this.io.local();
            const remote = await this.io.read(before.cartId);
            const current = this.io.local();
            if(current.cartId !== before.cartId) return;
            if(!current.cartDirty || sameItems(current.items, remote.items)) this.accept(remote);
            else if((current.baseKnown && current.baseRevision === remote.revision) || (!current.baseKnown && remote.revision === null)) {
                this.io.patch({baseKnown: true, baseRevision: remote.revision});
                this.io.succeeded();
            } else this.io.patch({cartSyncConflict: true});
            this.ready = true;
            this.io.initialized();
        }
        while(this.io.local().cartDirty && !this.io.local().cartSyncConflict) {
            const current = this.io.local();
            const pending: CartServerUpdate = {
                items: JSON.parse(JSON.stringify(normalizeCartItems(current.items))) as CartItem[],
                expected_revision: current.baseRevision, operation_id: this.io.operationId(),
            };
            // Persist before sending. A lost acknowledgement must reuse this body/ID.
            this.io.patch({pendingWrite: pending});
            await this.transmit();
        }
    }

    initialize = (): Promise<void> => {
        if(this.initialization) return this.initialization;
        this.initialization = this.enqueue(() => this.run()).finally(() => {this.initialization = null});
        return this.initialization;
    };

    save = (): Promise<void> => {
        if(this.saving) return this.saving;
        this.saving = this.enqueue(() => this.run()).finally(() => {this.saving = null});
        return this.saving;
    };

    resolve = (choice: 'server' | 'local'): Promise<void> => this.enqueue(async () => {
        const before = this.io.local();
        const remote = await this.io.read(before.cartId);
        const current = this.io.local();
        if(current.cartId !== before.cartId) return;
        this.ready = true;
        this.io.initialized();
        if(choice === 'server') {
            if(current.items !== before.items) {this.io.patch({cartSyncConflict: true}); return}
            this.accept(remote);
        } else {
            this.io.patch({baseKnown: true, baseRevision: remote.revision, pendingWrite: null,
                cartDirty: true, cartSyncConflict: false});
            await this.run();
        }
    });
}
