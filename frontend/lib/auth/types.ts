export interface AuthUser {
    id: number;
    email: string;
    first_name?: string;
    last_name?: string;
    username?: string;
    gender?: string;
    birth_date?: string;
    phone?: string;
}

export type AuthStep = 'input' | 'verify';
export type DashboardTab = 'profile' | 'orders' | 'settings';
export type EmailLinkStep = 'start' | 'input' | 'verify';

export interface AuthSessionResponse {
    token: string;
    user: AuthUser;
}

export interface AuthAccessResponse {
    roles: string[];
    permissions: string[];
}

export interface EmailCodeRequestResponse {
    testing_only_otp?: string;
}

export interface AuthOrderItem {
    image?: string;
    title: string;
    size?: string;
    color?: string;
    customization?: {
        fit?: {
            sleeveMode?: 'standard' | 'height';
            lengthCm?: number;
            widthCm?: number;
        };
    };
}

export interface AuthOrderSummary {
    id: number;
    total_price: number | string;
    created_at: string;
    status: string;
    payment_status: string;
    customer_stage?: string | null;
    customer_stage_label?: string | null;
    cdek_number?: string | null;
    cdek_status?: string | null;
}

export interface AuthOrder extends AuthOrderSummary {
    cart_items: string | null;
}

export interface AuthOrderPage {
    items: AuthOrderSummary[];
    next_cursor: number | null;
}

export interface AuthProfileData {
    first_name: string;
    gender: string;
    birth_date: string;
    phone: string;
    email: string;
}
