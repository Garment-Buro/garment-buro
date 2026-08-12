import type { ConstructorCustomization } from '@/lib/constructor/types';

export interface CartItem {
    id: string;
    product_id: number;
    title: string;
    price: number;
    image: string;
    size: string;
    color: string;
    quantity: number;
    customization?: ConstructorCustomization;
}

export interface CartServerPayload {
    cart_id: string;
    items: CartItem[];
    updated_at_ms: number;
}

export interface CartServerUpdate {
    items: CartItem[];
    updated_at_ms: number;
}
