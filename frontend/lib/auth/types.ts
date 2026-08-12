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

export type AuthMethod = 'email' | 'telegram';
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

export interface AuthOrder {
    id: number;
    total_price: number | string;
    created_at: string;
    cart_items: string;
    cdek_number?: string;
    cdek_status?: string;
}

export interface AuthProfileData {
    first_name: string;
    gender: string;
    birth_date: string;
    phone: string;
    email: string;
}
