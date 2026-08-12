'use client';

import { useEffect } from 'react';

import { authSessionChannel } from '@/lib/auth/sessionChannel';
import { useAuthStore } from '@/store/authStore';

export const AuthSessionBootstrap = () => {
    const sessionRestorePending = useAuthStore(state => state.sessionRestorePending);
    const logoutPending = useAuthStore(state => state.logoutPending);

    useEffect(() => {
        const initialize = () => {
            void useAuthStore.getState().initializeSession();
        };
        const unsubscribeChannel = authSessionChannel.subscribe(message => {
            const state = useAuthStore.getState();
            if (message.type === 'session') {
                state.acceptRemoteSession(message.session, message.generation);
            } else {
                state.acceptRemoteLogout(message.pending);
            }
        });
        const unsubscribeHydration = useAuthStore.persist.hasHydrated()
            ? undefined
            : useAuthStore.persist.onFinishHydration(initialize);
        if (useAuthStore.persist.hasHydrated()) initialize();

        const handleOnline = () => {
            const state = useAuthStore.getState();
            if (state.logoutPending || !state.isAuthenticated) initialize();
        };
        window.addEventListener('online', handleOnline);
        return () => {
            unsubscribeChannel();
            unsubscribeHydration?.();
            window.removeEventListener('online', handleOnline);
        };
    }, []);

    useEffect(() => {
        if (!sessionRestorePending && !logoutPending) return;
        const retry = () => {
            if (navigator.onLine) {
                void useAuthStore.getState().initializeSession();
            }
        };
        const timer = window.setInterval(retry, 15_000);
        return () => window.clearInterval(timer);
    }, [logoutPending, sessionRestorePending]);

    return null;
};
