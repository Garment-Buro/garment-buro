import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { getCartSnapshot, syncCartSnapshot } from '@/lib/api/cart'
import type { CartItem } from '@/lib/cart/types'
import type { CheckoutItemPrice } from '@/lib/api/checkoutPrices'
import { browserLocalStorage, createBrowserStateStorage } from '@/lib/browser/utils/storage'
import { CartSnapshotSync, type CartSyncState } from '@/lib/cart/snapshotSync'
import {
    createCartId,
    getActiveCartItemId,
    getCartItemsTotal,
    normalizeCartItem,
} from '@/lib/cart/utils/cart'

export type { CartItem } from '@/lib/cart/types'

interface CartState extends CartSyncState {
    isCartOpen: boolean;
    activeItemId: string | null;
    cartId: string;
    hasHydrated: boolean;
    isCartInitialized: boolean;
    cartSyncError: boolean;
    setHasHydrated: (hasHydrated: boolean) => void;
    ensureCartId: () => string;
    setIsCartOpen: (isOpen: boolean) => void;
    setActiveItemId: (id: string | null) => void;
    addItem: (item: Omit<CartItem, 'id'>) => void;
    updateItem: (id: string, item: Omit<CartItem, 'id'>) => void;
    removeItem: (id: string) => void;
    updateQuantity: (id: string, newQuantity: number) => void;
    applyCheckoutPrices: (expectedItems: CartItem[], prices: CheckoutItemPrice[]) => boolean;
    clearCart: () => void;
    getTotalPrice: () => number;
    initializeCart: () => Promise<void>;
    syncCartToServer: (opts?: { immediate?: boolean }) => Promise<void>;
    retryCartSync: () => Promise<void>;
    resolveCartConflict: (choice: 'server' | 'local') => Promise<void>;
}

const CART_SYNC_DEBOUNCE_MS = 250;

export const useCartStore = create<CartState>()(
    persist(
        (set, get) => {
            let cartSyncTimer: ReturnType<typeof setTimeout> | null = null;
            const sync = new CartSnapshotSync({
                local: () => {
                    const state = get();
                    return { ...state, cartId: state.ensureCartId() };
                },
                read: getCartSnapshot,
                write: syncCartSnapshot,
                operationId: () => window.crypto.randomUUID().replaceAll('-', ''),
                patch: update => set(state => ({
                    ...update,
                    ...(update.items ? {
                        activeItemId: getActiveCartItemId(update.items, state.activeItemId),
                        isCartOpen: update.items.length > 0 && state.isCartOpen,
                    } : {}),
                })),
                initialized: () => set({ isCartInitialized: true }),
                failed: () => set({ cartSyncError: true }),
                succeeded: () => set({ cartSyncError: false }),
            });
            return {
                items: [],
                isCartOpen: false,
                activeItemId: null,
                cartId: '',
                baseRevision: null,
                baseKnown: false,
                cartDirty: false,
                pendingWrite: null,
                cartSyncConflict: false,
                hasHydrated: false,
                isCartInitialized: false,
                cartSyncError: false,
                setHasHydrated: (hasHydrated) => set({ hasHydrated }),
                ensureCartId: () => {
                    const currentId = get().cartId;
                    if (currentId) return currentId;
                    const newId = createCartId(typeof window !== 'undefined' ? window.crypto : undefined);
                    set({ cartId: newId });
                    return newId;
                },
                setIsCartOpen: (isOpen) => set({ isCartOpen: isOpen }),
                setActiveItemId: (id) => set((state) => ({
                    activeItemId: getActiveCartItemId(state.items, id),
                })),

                addItem: (newItem) => {
                    const id = newItem.customization?.kind === 'constructor'
                        ? `design_${createCartId(typeof window !== 'undefined' ? window.crypto : undefined)}`
                        : `${newItem.product_id}_${newItem.size}_${newItem.color}`;
                    set((state) => {
                        const existingItem = state.items.find(item => item.id === id);

                        if (existingItem) {
                            const nextItems = state.items.map(item =>
                                item.id === id ? { ...item, quantity: item.quantity + newItem.quantity } : item
                            );

                            return {
                                isCartOpen: false,
                                activeItemId: id,
                                cartDirty: true,
                                items: nextItems,
                            }
                        }

                        const nextItems = [...state.items, { ...newItem, id }];

                        return {
                            isCartOpen: false,
                            activeItemId: id,
                            cartDirty: true,
                            items: nextItems,
                        }
                    })
                    void get().syncCartToServer();
                },

                updateItem: (id, item) => {
                    const normalizedItem = normalizeCartItem({ ...item, id });

                    set((state) => {
                        const existingItem = state.items.find(cartItem => cartItem.id === id);
                        const nextItems = existingItem
                            ? state.items.map(cartItem => cartItem.id === id ? normalizedItem : cartItem)
                            : [...state.items, normalizedItem];

                        return {
                            isCartOpen: false,
                            activeItemId: id,
                            cartDirty: true,
                            items: nextItems,
                        };
                    });

                    void get().syncCartToServer();
                },

                removeItem: (id) => {
                    set((state) => {
                        const nextItems = state.items.filter(item => item.id !== id);
                        const nextActiveItemId = state.activeItemId === id
                            ? nextItems[nextItems.length - 1]?.id || null
                            : getActiveCartItemId(nextItems, state.activeItemId);

                        return {
                            activeItemId: nextActiveItemId,
                            isCartOpen: nextItems.length > 0 ? state.isCartOpen : false,
                            cartDirty: true,
                            items: nextItems,
                        };
                    })
                    void get().syncCartToServer();
                },

                updateQuantity: (id, newQuantity) => {
                    set((state) => {
                        if (newQuantity <= 0) {
                            const nextItems = state.items.filter(item => item.id !== id);
                            const nextActiveItemId = state.activeItemId === id
                                ? nextItems[nextItems.length - 1]?.id || null
                                : getActiveCartItemId(nextItems, state.activeItemId);

                            return {
                                activeItemId: nextActiveItemId,
                                isCartOpen: nextItems.length > 0 ? state.isCartOpen : false,
                                cartDirty: true,
                                items: nextItems,
                            };
                        }

                        const nextItems = state.items.map(item =>
                            item.id === id ? { ...item, quantity: newQuantity } : item
                        );

                        return {
                            activeItemId: getActiveCartItemId(nextItems, id),
                            cartDirty: true,
                            items: nextItems,
                        };
                    })
                    void get().syncCartToServer();
                },

                applyCheckoutPrices: (expectedItems, prices) => {
                    // Reference comparison also detects edits followed by undo, or a
                    // late cart initialization. Never overwrite a newer snapshot.
                    if (get().items !== expectedItems || prices.length !== expectedItems.length) return false;
                    const byId = new Map(prices.map(price => [price.id, price]));
                    if (byId.size !== expectedItems.length || expectedItems.some(item => byId.get(item.id)?.productId !== item.product_id)) return false;
                    const items = expectedItems.map(item => ({ ...item, price: byId.get(item.id)!.price }));
                    set({ items, cartDirty: true });
                    void get().syncCartToServer();
                    return true;
                },

                clearCart: () => {
                    set({ activeItemId: null, isCartOpen: false, items: [], cartDirty: true })
                    void get().syncCartToServer({ immediate: true });
                },

                getTotalPrice: () => {
                    return getCartItemsTotal(get().items);
                },

                initializeCart: async () => {
                    if (typeof window === 'undefined' || !get().hasHydrated || get().isCartInitialized) return;
                    const state = get();
                    // There is no remote document to restore before an ID or edit exists.
                    // Keep the sync queue uninitialized so the first edit still reads
                    // its allocated ID before the normal versioned write.
                    if (!state.cartId && !state.items.length && !state.cartDirty && !state.pendingWrite
                        && !state.baseKnown && state.baseRevision === null && !state.cartSyncConflict) {
                        set({ isCartInitialized: true });
                        return;
                    }
                    await sync.initialize();
                },

                syncCartToServer: async (opts) => {
                    if (typeof window === 'undefined' || !get().hasHydrated) return;

                    const immediate = opts?.immediate === true;
                    if (!immediate) {
                        if (cartSyncTimer) clearTimeout(cartSyncTimer);
                        cartSyncTimer = setTimeout(() => {
                            void get().syncCartToServer({ immediate: true });
                        }, CART_SYNC_DEBOUNCE_MS);
                        return;
                    }

                    if (cartSyncTimer) {
                        clearTimeout(cartSyncTimer);
                        cartSyncTimer = null;
                    }

                    await sync.save();
                },
                resolveCartConflict: choice => sync.resolve(choice),
                retryCartSync: async () => {
                    if (!get().isCartInitialized) await get().initializeCart();
                    else await get().syncCartToServer({ immediate: true });
                },
            };
        },
        {
            name: 'garment-buro-cart-storage',
            version: 1,
            migrate: persisted => {
                const old = persisted as Partial<CartState> & {lastUpdatedAt?: number};
                return {items: old.items ?? [], activeItemId: old.activeItemId ?? null, cartId: old.cartId ?? '',
                    baseKnown: false, baseRevision: null, cartDirty: Boolean(old.items?.length || old.lastUpdatedAt), pendingWrite: null};
            },
            storage: createBrowserStateStorage<Pick<CartState, 'items' | 'activeItemId' | 'cartId' | 'baseKnown' | 'baseRevision' | 'cartDirty' | 'pendingWrite'>>(browserLocalStorage),
            partialize: state => ({
                items: state.items, activeItemId: state.activeItemId, cartId: state.cartId,
                baseKnown: state.baseKnown, baseRevision: state.baseRevision, cartDirty: state.cartDirty, pendingWrite: state.pendingWrite,
            }),
            onRehydrateStorage: () => (state) => {
                state?.setHasHydrated(true);
            },
        }
    )
)
