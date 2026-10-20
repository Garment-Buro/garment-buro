import type { CartItem } from '../types.ts';

export const getActiveCartItem = (
    items: readonly CartItem[],
    activeItemId: string | null,
) => (activeItemId ? items.find(item => item.id === activeItemId) : undefined) ?? items[items.length - 1];
