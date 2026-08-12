import { create } from 'zustand';

import { getAuthAccess } from '@/lib/api/auth';
import { ApiError } from '@/lib/api/http';
import type { AuthAccessResponse } from '@/lib/auth/types';
import { useAuthStore } from '@/store/authStore';

export type IdentityAccessStatus = 'idle' | 'loading' | 'ready' | 'denied' | 'error';

type IdentityAccessState = {
    userId: number | null;
    status: IdentityAccessStatus;
    access: AuthAccessResponse | null;
    loadedAt: number | null;
    reset: () => void;
    ensure: (userId: number, force?: boolean) => Promise<void>;
};

const ACCESS_TTL_MS = 60_000;
let pending: { userId: number; promise: Promise<void> } | null = null;

const isAccessDenied = (error: unknown) => (
    error instanceof ApiError && (error.status === 401 || error.status === 403)
);

export const useIdentityAccessStore = create<IdentityAccessState>((set, get) => ({
    userId: null,
    status: 'idle',
    access: null,
    loadedAt: null,

    reset: () => {
        pending = null;
        set({ userId: null, status: 'idle', access: null, loadedAt: null });
    },

    ensure: async (userId, force = false) => {
        const current = get();
        const fresh = current.userId === userId
            && current.status === 'ready'
            && current.loadedAt !== null
            && Date.now() - current.loadedAt < ACCESS_TTL_MS;
        if (!force && fresh) return;
        if (pending?.userId === userId) return pending.promise;

        set({ userId, status: 'loading', access: null, loadedAt: null });
        const promise = useAuthStore.getState()
            .runAuthenticated(token => getAuthAccess(token))
            .then((access) => {
                if (useAuthStore.getState().user?.id !== userId) return;
                set({ userId, status: 'ready', access, loadedAt: Date.now() });
            })
            .catch((error: unknown) => {
                if (useAuthStore.getState().user?.id !== userId) return;
                set({
                    userId,
                    status: isAccessDenied(error) ? 'denied' : 'error',
                    access: null,
                    loadedAt: null,
                });
            })
            .finally(() => {
                if (pending?.promise === promise) pending = null;
            });
        pending = { userId, promise };
        return promise;
    },
}));
