import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import {
    logoutAuthSession,
    migrateLegacyAuthSession,
    refreshAuthSession,
} from '@/lib/api/auth';
import { ApiError } from '@/lib/api/http';
import { isIdentitySessionV2Enabled } from '@/lib/auth/config';
import { authSessionChannel, withAuthRefreshLock } from '@/lib/auth/sessionChannel';
import { AuthSessionCoordinator } from '@/lib/auth/sessionCoordinator';
import type { AuthSessionResponse, AuthUser } from '@/lib/auth/types';

export type User = AuthUser;
type AuthenticatedOperation<Result> = (token: string) => Promise<Result>;

export interface AuthState {
    token: string | null;
    user: User | null;
    isAuthenticated: boolean;
    isSessionReady: boolean;
    sessionRestorePending: boolean;
    logoutPending: boolean;
    sessionGeneration: string | null;
    setAuth: (token: string, user: User) => void;
    updateUser: (user: User) => void;
    initializeSession: () => Promise<void>;
    runAuthenticated: <Result>(operation: AuthenticatedOperation<Result>) => Promise<Result>;
    logout: () => Promise<void>;
    acceptRemoteSession: (session: AuthSessionResponse, generation: string) => void;
    acceptRemoteLogout: (pending: boolean) => void;
}

type PersistedAuthState = Partial<Pick<
    AuthState,
    'token' | 'user' | 'isAuthenticated' | 'logoutPending'
>>;

const sessionV2Enabled = isIdentitySessionV2Enabled();
const coordinator = new AuthSessionCoordinator(refreshAuthSession, logoutAuthSession);
let initializationPromise: Promise<void> | null = null;

const unauthorized = (error: unknown) => error instanceof ApiError && error.status === 401;
const migrationUnavailable = (error: unknown) => (
    error instanceof ApiError && (error.status === 401 || error.status === 404)
);

export const useAuthStore = create<AuthState>()(
    persist(
        (set, get) => {
            const clearSession = (logoutPending = false) => set({
                token: null,
                user: null,
                isAuthenticated: false,
                isSessionReady: true,
                sessionRestorePending: false,
                logoutPending,
                sessionGeneration: null,
            });

            const applySession = (
                session: AuthSessionResponse,
                generation?: string,
            ) => {
                const nextGeneration = generation || (
                    sessionV2Enabled ? authSessionChannel.publishSession(session) : null
                );
                set({
                    token: session.token,
                    user: session.user,
                    isAuthenticated: true,
                    isSessionReady: true,
                    sessionRestorePending: false,
                    logoutPending: false,
                    sessionGeneration: nextGeneration,
                });
                return session;
            };

            const currentSession = () => {
                const state = get();
                if (!state.token || !state.user) return null;
                return { token: state.token, user: state.user };
            };

            const refreshWithCrossTabLock = (
                staleToken: string | null,
                migrateToken?: string,
            ) => withAuthRefreshLock(async () => {
                const current = currentSession();
                if (current && staleToken && current.token !== staleToken) return current;

                const state = get();
                const sharedGeneration = authSessionChannel.getSharedGeneration();
                if (sharedGeneration && sharedGeneration !== state.sessionGeneration) {
                    const remote = await authSessionChannel.waitForSession(sharedGeneration);
                    if (remote) return applySession(remote, sharedGeneration);
                }

                let session: AuthSessionResponse;
                if (migrateToken) {
                    try {
                        session = await migrateLegacyAuthSession(migrateToken);
                    } catch (error) {
                        if (!migrationUnavailable(error)) throw error;
                        session = await coordinator.refresh();
                    }
                } else {
                    session = await coordinator.refresh();
                }
                return applySession(session);
            });

            const completePendingLogout = async () => {
                try {
                    await coordinator.logout();
                } catch {
                    set({ isSessionReady: true, logoutPending: true });
                    return;
                }
                clearSession(false);
                authSessionChannel.publishLogout(false);
            };

            return {
                token: null,
                user: null,
                isAuthenticated: false,
                isSessionReady: !sessionV2Enabled,
                sessionRestorePending: false,
                logoutPending: false,
                sessionGeneration: null,

                setAuth: (token, user) => {
                    applySession({ token, user });
                },

                updateUser: (user) => {
                    const token = get().token;
                    if (token && sessionV2Enabled) {
                        applySession({ token, user });
                    } else {
                        set({ user });
                    }
                },

                initializeSession: async () => {
                    if (!sessionV2Enabled) {
                        set({ isSessionReady: true });
                        return;
                    }
                    if (initializationPromise) return initializationPromise;
                    initializationPromise = (async () => {
                        const state = get();
                        if (state.logoutPending) {
                            await completePendingLogout();
                            return;
                        }
                        try {
                            await refreshWithCrossTabLock(
                                state.token,
                                state.token || undefined,
                            );
                        } catch (error) {
                            if (migrationUnavailable(error)) clearSession(false);
                            else set({ isSessionReady: true, sessionRestorePending: true });
                        }
                    })().finally(() => {
                        initializationPromise = null;
                    });
                    return initializationPromise;
                },

                runAuthenticated: async <Result,>(operation: AuthenticatedOperation<Result>) => {
                    let token = get().token;
                    if (!token) {
                        if (!sessionV2Enabled) throw new ApiError('Authentication required', 401);
                        token = (await refreshWithCrossTabLock(null)).token;
                    }
                    try {
                        return await operation(token);
                    } catch (error) {
                        if (!sessionV2Enabled || !unauthorized(error)) throw error;
                    }

                    try {
                        const refreshed = await refreshWithCrossTabLock(token);
                        return await operation(refreshed.token);
                    } catch (error) {
                        if (migrationUnavailable(error)) {
                            clearSession(false);
                            authSessionChannel.publishLogout(false);
                        }
                        throw error;
                    }
                },

                logout: async () => {
                    if (!sessionV2Enabled) {
                        clearSession(false);
                        return;
                    }
                    clearSession(true);
                    authSessionChannel.publishLogout(true);
                    await completePendingLogout();
                },

                acceptRemoteSession: (session, generation) => {
                    applySession(session, generation);
                },

                acceptRemoteLogout: (pending) => {
                    clearSession(pending);
                },
            };
        },
        {
            name: 'auth-storage',
            version: 2,
            partialize: (state): PersistedAuthState => (
                sessionV2Enabled
                    ? { logoutPending: state.logoutPending }
                    : {
                        token: state.token,
                        user: state.user,
                        isAuthenticated: state.isAuthenticated,
                    }
            ),
            migrate: (persistedState): PersistedAuthState => {
                const previous = (persistedState || {}) as PersistedAuthState;
                if (!sessionV2Enabled) return previous;
                return {
                    token: previous.token || null,
                    user: previous.user || null,
                    isAuthenticated: Boolean(previous.token && previous.user),
                    logoutPending: Boolean(previous.logoutPending),
                };
            },
        },
    ),
);
