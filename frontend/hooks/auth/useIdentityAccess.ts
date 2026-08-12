'use client';

import { useCallback, useEffect } from 'react';

import { isCrmCabinetEnabled } from '@/lib/auth/config';
import { useAuthStore } from '@/store/authStore';
import { useIdentityAccessStore } from '@/store/identityAccessStore';

export const useIdentityAccess = () => {
    const enabled = isCrmCabinetEnabled();
    const isSessionReady = useAuthStore(state => state.isSessionReady);
    const userId = useAuthStore(state => state.user?.id ?? null);
    const status = useIdentityAccessStore(state => state.status);
    const access = useIdentityAccessStore(state => state.access);
    const ensure = useIdentityAccessStore(state => state.ensure);
    const reset = useIdentityAccessStore(state => state.reset);

    useEffect(() => {
        if (!enabled || !isSessionReady) return;
        if (userId === null) {
            reset();
            return;
        }
        void ensure(userId);
    }, [enabled, ensure, isSessionReady, reset, userId]);

    const retry = useCallback(() => {
        if (userId !== null) void ensure(userId, true);
    }, [ensure, userId]);

    return {
        enabled,
        isSessionReady,
        isAuthenticated: userId !== null,
        status,
        access,
        hasCrmAccess: status === 'ready' && Boolean(access?.permissions.includes('crm.access')),
        retry,
    };
};
