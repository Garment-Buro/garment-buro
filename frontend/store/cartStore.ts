import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { getCartSnapshot, syncCartSnapshot } from '@/lib/api/cart'
import type { CartItem } from '@/lib/cart/types'
import {
    createCartId,
    getActiveCartItemId,
    getCartItemsTotal,
    normalizeCartItem,
    normalizeCartItems,
} from '@/lib/cart/utils/cart'

export type { CartItem } from '@/lib/cart/types'

interface CartState {
    items: CartItem[];
    isCartOpen: boolean;
    activeItemId: string | null;
    cartId: string;
    lastUpdatedAt: number;
    hasHydrated: boolean;
    isCartInitialized: boolean;
    setHasHydrated: (hasHydrated: boolean) => void;
    ensureCartId: () => string;
    setIsCartOpen: (isOpen: boolean) => void;
    setActiveItemId: (id: string | null) => void;
    addItem: (item: Omit<CartItem, 'id'>) => void;
    updateItem: (id: string, item: Omit<CartItem, 'id'>) => void;
    removeItem: (id: string) => void;
    updateQuantity: (id: string, newQuantity: number) => void;
    clearCart: () => void;
    getTotalPrice: () => number;
    initializeCart: () => Promise<void>;
    syncCartToServer: (opts?: { immediate?: boolean }) => Promise<void>;
}

const CART_SYNC_DEBOUNCE_MS = 250;
let cartSyncTimer: ReturnType<typeof setTimeout> | null = null;
let cartInitializationPromise: Promise<void> | null = null;

export const useCartStore = create<CartState>()(
    persist(
        (set, get) => ({
            items: [],
            isCartOpen: false,
            activeItemId: null,
            cartId: '',
            lastUpdatedAt: 0,
            hasHydrated: false,
            isCartInitialized: false,
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
                const id = `${newItem.product_id}_${newItem.size}_${newItem.color}`;
                set((state) => {
                    const existingItem = state.items.find(item => item.id === id);
                    const lastUpdatedAt = Date.now();

                    if (existingItem) {
                        const nextItems = state.items.map(item =>
                            item.id === id ? { ...item, quantity: item.quantity + newItem.quantity } : item
                        );

                        return {
                            isCartOpen: false,
                            activeItemId: id,
                            lastUpdatedAt,
                            items: nextItems,
                        }
                    }

                    const nextItems = [...state.items, { ...newItem, id }];

                    return {
                        isCartOpen: false,
                        activeItemId: id,
                        lastUpdatedAt,
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
                        lastUpdatedAt: Date.now(),
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
                        lastUpdatedAt: Date.now(),
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
                            lastUpdatedAt: Date.now(),
                            items: nextItems,
                        };
                    }

                    const nextItems = state.items.map(item =>
                        item.id === id ? { ...item, quantity: newQuantity } : item
                    );

                    return {
                        activeItemId: getActiveCartItemId(nextItems, id),
                        lastUpdatedAt: Date.now(),
                        items: nextItems,
                    };
                })
                void get().syncCartToServer();
            },

            clearCart: () => {
                set({ activeItemId: null, isCartOpen: false, items: [], lastUpdatedAt: Date.now() })
                void get().syncCartToServer({ immediate: true });
            },

            getTotalPrice: () => {
                return getCartItemsTotal(get().items);
            },

            initializeCart: async () => {
                if (typeof window === 'undefined' || !get().hasHydrated) return;

                if (cartInitializationPromise) {
                    return cartInitializationPromise;
                }

                cartInitializationPromise = (async () => {
                    const cartId = get().ensureCartId();
                    const localItems = get().items;
                    const localUpdatedAt = get().lastUpdatedAt || 0;

                    try {
                        const payload = await getCartSnapshot(cartId);
                        if (!payload) return;
                        const serverItems = normalizeCartItems(payload.items || []);
                        const serverUpdatedAt = Number(payload.updated_at_ms || 0);

                        if (serverItems.length === 0) {
                            if (localItems.length > 0) {
                                await get().syncCartToServer({ immediate: true });
                            }
                            return;
                        }

                        if (localItems.length === 0 || serverUpdatedAt > localUpdatedAt) {
                            set({
                                activeItemId: getActiveCartItemId(serverItems, get().activeItemId),
                                items: serverItems,
                                lastUpdatedAt: serverUpdatedAt || Date.now(),
                            });
                            return;
                        }

                        if (localUpdatedAt >= serverUpdatedAt) {
                            await get().syncCartToServer({ immediate: true });
                        }
                    } catch (error) {
                        console.error('Failed to initialize cart from server:', error);
                    } finally {
                        set({ isCartInitialized: true });
                        cartInitializationPromise = null;
                    }
                })();

                return cartInitializationPromise;
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

                const cartId = get().ensureCartId();
                const items = normalizeCartItems(get().items);
                const updatedAt = get().lastUpdatedAt || Date.now();

                try {
                    await syncCartSnapshot(cartId, { items, updated_at_ms: updatedAt });
                } catch (error) {
                    console.error('Failed to sync cart to server:', error);
                }
            },
        }),
        {
            name: 'garment-buro-cart-storage',
            partialize: (state) => ({
                items: state.items,
                activeItemId: state.activeItemId,
                cartId: state.cartId,
                lastUpdatedAt: state.lastUpdatedAt,
            }),
            onRehydrateStorage: () => (state) => {
                state?.setHasHydrated(true);
            },
        }
    )
)
