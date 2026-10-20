'use client';

import { useAuthStore } from '@/store/authStore';

export function useCustomerAccount() {
    const userId = useAuthStore(state => state.user?.id ?? null);
    const ready = useAuthStore(state => state.isSessionReady && state.isAuthenticated);
    const sessionReady = useAuthStore(state => state.isSessionReady);
    const epoch = useAuthStore(state => state.accountEpoch);
    return {userId:ready ? userId : null, key:ready && userId ? `${userId}:${epoch ?? 'session'}` : null, sessionReady};
}

export function isCustomerSessionCurrent(userId: number, sessionKey?: string | null) {
    const current = useAuthStore.getState();
    return current.isSessionReady && current.isAuthenticated && current.user?.id === userId
        && (sessionKey == null || sessionKey === `${userId}:${current.accountEpoch ?? 'session'}`);
}

export function runForCustomer<Result>(userId: number, operation: (token: string) => Promise<Result>, sessionKey?: string | null) {
    return useAuthStore.getState().runAuthenticated(async token => {
        if(!isCustomerSessionCurrent(userId, sessionKey)) {
            throw new DOMException('Customer session changed', 'AbortError');
        }
        const result = await operation(token);
        if(!isCustomerSessionCurrent(userId, sessionKey)) throw new DOMException('Customer session changed', 'AbortError');
        return result;
    });
}
