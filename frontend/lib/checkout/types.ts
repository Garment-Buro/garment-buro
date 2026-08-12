export type CdekTariff = { delivery_sum?: number | string };
export type CdekAddress = { name?: string; address?: string; city?: string; formatted?: string; code?: string };
export type CdekGoodsItem = { width: number; height: number; length: number; weight: number };
export type CdekLoadState = 'idle' | 'loading' | 'loaded' | 'error';
export type CdekSelection = { address: string; city: string; deliveryType: string; cdekCode?: string };

export type DeliveryCalculationRequest = {
    city: string;
    delivery_method: string;
    cart_items: Array<{ product_id: number; quantity: number }>;
};

export type DeliveryCalculationResponse = {
    delivery_price?: number;
    period_min?: number;
    period_max?: number;
    tariff_code?: number;
    currency?: 'RUB';
};

export type CheckoutOrderPayload = {
    email: string;
    phone: string;
    first_name: string;
    last_name: string;
    patronymic: string;
    delivery_city: string;
    delivery_method: string;
    delivery_address: string;
    payment_method: string;
    cart_items: string;
    total_price: number;
    delivery_price: number;
    cdek_point_code?: string;
};

export type CheckoutOrderResponse = { payment_url?: string; order_id: number };

export type CheckoutField = 'email' | 'phone' | 'firstName' | 'lastName' | 'patronymic'
    | 'deliveryCity' | 'deliveryAddress' | 'deliveryMethod' | 'cdekAddress' | 'cdekPointCode'
    | 'paymentMode' | 'agreeOffer' | 'agreePolicy';

export type CheckoutFormValues = {
    email: string;
    phone: string;
    firstName: string;
    lastName: string;
    patronymic: string;
    deliveryCity: string;
    deliveryAddress: string;
    deliveryMethod: string;
    cdekAddress: string;
    cdekPointCode: string;
    paymentMode: 'card' | 'qr';
    agreeOffer: boolean;
    agreePolicy: boolean;
};

export type CheckoutErrors = Partial<Record<'email' | 'phone' | 'firstName' | 'deliveryAddress' | 'agreeOffer' | 'agreePolicy', boolean>>;
