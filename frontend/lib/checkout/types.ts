export type DeliveryCalculationRequest = {
    city: string;
    delivery_method: string;
    cart_items: Array<{ product_id: number; quantity: number }>;
    cdek_point_code?: string;
    delivery_address?: string;
};

export type DeliveryCalculationResponse = {
    delivery_price: number;
    quote_token: string;
    delivery_city: string;
    delivery_address: string;
    cdek_point_code: string | null;
    period_min?: number;
    period_max?: number;
    tariff_code: number;
    currency: 'RUB';
};

export type CheckoutOrderPayload = {
    buyer: import('./contact').CheckoutContact;
    recipient: import('./contact').CheckoutContact;
    delivery_city: string;
    delivery_method: string;
    delivery_address: string;
    payment_method: string;
    items: import('../cart/types').CartItem[];
    claimed_total_price: number;
    delivery_price: number;
    delivery_quote_token: string;
    cdek_point_code?: string;
    currency: 'RUB';
};

export type CheckoutOrderResponse = { payment_url?: string | null; order_id: number };
export type CheckoutActor = { kind: 'customer' | 'guest'; token: string };
export type CheckoutRequestContext = { idempotencyKey: string; actor: CheckoutActor };
