import type {
    AuthAccessResponse,
    AuthOrder,
    AuthProfileData,
    AuthSessionResponse,
    AuthUser,
    EmailCodeRequestResponse,
} from '@/lib/auth/types';

import { request, requestJson } from './http';

const jsonHeaders = (token?: string | null) => ({
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
});

export const requestAuthEmailCode = (email: string) => requestJson<EmailCodeRequestResponse>(
    '/auth/email/request',
    { method: 'POST', headers: jsonHeaders(), body: JSON.stringify({ email }) },
);

export const verifyAuthEmailCode = (email: string, code: string) => requestJson<AuthSessionResponse>(
    '/auth/email/verify',
    { method: 'POST', headers: jsonHeaders(), body: JSON.stringify({ email, code }) },
);

export const refreshAuthSession = () => requestJson<AuthSessionResponse>(
    '/auth/refresh',
    { method: 'POST', headers: jsonHeaders() },
);

export const migrateLegacyAuthSession = (token: string) => requestJson<AuthSessionResponse>(
    '/auth/session/migrate',
    { method: 'POST', headers: jsonHeaders(token) },
);

export const logoutAuthSession = async () => {
    await request('/auth/logout', {
        method: 'POST',
        headers: jsonHeaders(),
    });
};

export const getAuthOrders = (token: string, signal?: AbortSignal) => requestJson<AuthOrder[]>(
    '/auth/orders',
    { headers: { Authorization: `Bearer ${token}` }, signal },
);

export const getAuthAccess = (token: string, signal?: AbortSignal) => requestJson<AuthAccessResponse>(
    '/auth/access',
    { headers: { Authorization: `Bearer ${token}` }, signal },
);

export const updateAuthProfile = (token: string, profile: AuthProfileData) => requestJson<AuthUser>(
    '/auth/me',
    { method: 'PUT', headers: jsonHeaders(token), body: JSON.stringify(profile) },
);

export const deleteAuthProfile = async (token: string) => {
    await request('/auth/me', {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
    });
};

export const requestAuthEmailLink = (token: string, email: string) => requestJson<EmailCodeRequestResponse>(
    '/auth/me/email/request',
    { method: 'POST', headers: jsonHeaders(token), body: JSON.stringify({ email }) },
);

export const verifyAuthEmailLink = (token: string, email: string, code: string) => requestJson<AuthUser>(
    '/auth/me/email/verify',
    { method: 'POST', headers: jsonHeaders(token), body: JSON.stringify({ email, code }) },
);
