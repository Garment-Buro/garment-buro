import type { AuthOrderItem, AuthProfileData, AuthUser } from '@/lib/auth/types';

export const hasUsableAuthToken = (token: string | null): token is string => (
    Boolean(token && token !== 'null' && token !== 'undefined')
);

export const parseAuthOrderItems = (cartJson: string): AuthOrderItem[] => {
    try {
        const parsed: unknown = JSON.parse(cartJson);
        return Array.isArray(parsed) ? parsed as AuthOrderItem[] : [];
    } catch {
        return [];
    }
};

export const getAuthOrderFitSummary = (item: AuthOrderItem) => {
    const fit = item.customization?.fit;
    if (!fit) return null;

    const sleeveLabel = fit.sleeveMode === 'height' ? 'под рост' : 'стандартные';
    return `Посадка: длина ${fit.lengthCm}, ширина ${fit.widthCm}, рукава ${sleeveLabel}`;
};

export const createAuthProfileData = (user: AuthUser | null): AuthProfileData => ({
    first_name: user?.first_name || '',
    gender: user?.gender || '',
    birth_date: user?.birth_date || '',
    phone: user?.phone || '',
    email: user?.email || '',
});

export const normalizeOtpDigit = (value: string) => value.replace(/\D/g, '').slice(-1);
export const normalizeOtpCode = (value: string) => value.replace(/\D/g, '').slice(0, 4);

