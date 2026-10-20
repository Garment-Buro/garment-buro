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
    total_price: number | string;
    created_at: string;
    delivery_method?: string | null;
    cart_items?: string | OrderItem[] | null;
    payment_status?: string | null;
    customer_stage?: string | null;
    customer_stage_label?: string | null;
    cdek_number?: string | null;
    cdek_status?: string | null;
}

export interface OrderDetailRow {
    label: string;
    value: string;
}
