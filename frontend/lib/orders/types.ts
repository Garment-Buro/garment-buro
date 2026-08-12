export interface AdminOrder {
    id: number;
    email: string;
    phone: string;
    first_name: string;
    last_name: string;
    total_price: number;
    status: string;
    created_at: string;
}

export interface OrderItemFit {
    lengthCm: number;
    widthCm: number;
    sleeveMode?: string;
}

export interface OrderItem {
    title: string;
    price: number;
    quantity: number;
    size?: string;
    color?: string;
    customization?: {
        fit?: OrderItemFit;
    };
}

export interface OrderDetails {
    id: string | number;
    status: string;
    total_price: number;
    created_at: string;
    delivery_method: string;
    cart_items?: string | OrderItem[];
}

export interface OrderDetailRow {
    label: string;
    value: string;
}
