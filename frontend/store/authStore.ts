import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import {
    logoutAuthSession,
    migrateLegacyAuthSession,
    refreshAuthSession,
    verifyAuthEmailCode,
} from '@/lib/api/auth';
import { ApiError } from '@/lib/api/http';
import { isIdentitySessionV2Enabled } from '@/lib/auth/config';
import { authSessionChannel, withAuthRefreshLock } from '@/lib/auth/sessionChannel';
import { AuthSessionCoordinator } from '@/lib/auth/sessionCoordinator';
import type { AuthSessionResponse, AuthUser } from '@/lib/auth/types';
import { useCheckoutDetailsStore } from './checkoutDetailsStore';
import { browserLocalStorage, createBrowserStateStorage } from '@/lib/browser/utils/storage';

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
    // One login/account lifetime, independent of access-token rotations.
    accountEpoch: string | null;
    setAuth: (token: string, user: User) => void;
    authenticate: (email: string, code: string, signal?: AbortSignal) => Promise<void>;
    updateUser: (user: User) => void;
    initializeSession: () => Promise<void>;
    runAuthenticated: <Result>(operation: AuthenticatedOperation<Result>) => Promise<Result>;
    logout: () => Promise<void>;
    acceptRemoteSession: (session: AuthSessionResponse, generation: string, accountEpoch?: string) => void;
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
            // Access tokens rotate within one account lifetime. Explicit login,
            // logout and account changes revoke every operation from that lifetime.
            let sessionRevision = 0;
            const assertCurrentSession = (revision: number) => {
                const epoch = get().accountEpoch;
                if (revision !== sessionRevision || (sessionV2Enabled && epoch
                    && epoch !== authSessionChannel.getSharedAccountEpoch())) {
                    throw new DOMException('Session changed', 'AbortError');
                }
            };
            const forSession = async <Result,>(revision: number, operation: () => Promise<Result>) => {
                try { return await operation(); }
                finally { assertCurrentSession(revision); }
            };
            const captureSharedIntent = () => {
                const epoch = authSessionChannel.getSharedAccountEpoch();
                const generation = authSessionChannel.getSharedGeneration();
                return () => {
                    if (authSessionChannel.getSharedAccountEpoch() !== epoch
                        || (!epoch && authSessionChannel.getSharedGeneration() !== generation)) {
                        throw new DOMException('Session changed', 'AbortError');
                    }
                };
            };
            const clearSession = (logoutPending = false) => {
                sessionRevision++;
                useCheckoutDetailsStore.getState().clear();
                set({
                    token: null,
                    user: null,
                    isAuthenticated: false,
                    isSessionReady: true,
                    sessionRestorePending: false,
                    logoutPending,
                    sessionGeneration: null,
                    accountEpoch: null,
                });
            };

            const applySession = (
                session: AuthSessionResponse,
                generation?: string,
                newLogin = false,
                sharedAccountEpoch?: string,
            ) => {
                const previous = get();
                if (previous.user && previous.user.id !== session.user.id) {
                    useCheckoutDetailsStore.getState().clear();
                }
                const accountEpoch = sharedAccountEpoch || (!newLogin && previous.isAuthenticated
                    && previous.user?.id === session.user.id && previous.accountEpoch
                    ? previous.accountEpoch : crypto.randomUUID());
                if (accountEpoch !== previous.accountEpoch) sessionRevision++;
                const nextGeneration = generation || (
                    sessionV2Enabled ? authSessionChannel.publishSession(session, accountEpoch) : null
                );
                set({
                    token: session.token,
                    user: session.user,
                    isAuthenticated: true,
                    isSessionReady: true,
                    sessionRestorePending: false,
                    logoutPending: false,
                    sessionGeneration: nextGeneration,
                    accountEpoch,
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
            ) => {
                const revision = sessionRevision;
                const assertSharedIntent = captureSharedIntent();
                return withAuthRefreshLock(async () => {
                    assertCurrentSession(revision);
                    assertSharedIntent();
                    const current = currentSession();
                    if (current && staleToken && current.token !== staleToken) return current;

                    const state = get();
                    const sharedGeneration = authSessionChannel.getSharedGeneration();
                    if (sharedGeneration && sharedGeneration !== state.sessionGeneration) {
                        const remote = await forSession(revision, () => authSessionChannel.waitForSession(sharedGeneration));
                        assertSharedIntent();
                        if (remote) return applySession(remote.session, sharedGeneration, false, remote.accountEpoch);
                    }

                    let session: AuthSessionResponse;
                    if (migrateToken) {
                        try {
                            session = await forSession(revision, () => migrateLegacyAuthSession(migrateToken));
                        } catch (error) {
                            if (!migrationUnavailable(error)) throw error;
                            session = await forSession(revision, () => coordinator.refresh(String(revision)));
                        }
                    } else {
                        session = await forSession(revision, () => coordinator.refresh(String(revision)));
                    }
                    // Restoring a cookie in a fresh tab is not a new login.
                    // Only an opaque lifetime marker is shared in browser storage.
                    assertSharedIntent();
                    return applySession(session, undefined, false,
                        authSessionChannel.getSharedAccountEpoch() || undefined);
                });
            };

            const completePendingLogout = async () => {
                const revision = sessionRevision;
                try {
                    await withAuthRefreshLock(async () => {
                        assertCurrentSession(revision);
                        await forSession(revision, () => coordinator.logout(String(revision)));
                        set({ isSessionReady: true, logoutPending: false });
                        authSessionChannel.publishLogout(false);
                    });
                } catch {
                    if (revision !== sessionRevision) return;
                    set({ isSessionReady: true, logoutPending: true });
                    return;
                }
            };

            return {
                token: null,
                user: null,
                isAuthenticated: false,
                isSessionReady: !sessionV2Enabled,
                sessionRestorePending: false,
                logoutPending: false,
                sessionGeneration: null,
                accountEpoch: null,

                setAuth: (token, user) => {
                    applySession({ token, user }, undefined, true);
                },

                authenticate: (email, code, signal) => {
                    const revision = sessionRevision;
                    const assertSharedIntent = captureSharedIntent();
                    const assertLoginIntent = () => {
                        assertCurrentSession(revision);
                        assertSharedIntent();
                    };
                    return withAuthRefreshLock(async () => {
                        signal?.throwIfAborted();
                        assertLoginIntent();
                        // Once verification starts, finish the cookie write and state
                        // publication together even if its form unmounts. Releasing
                        // the lock on UI cancellation could let a late Set-Cookie
                        // overwrite the next login.
                        const session = await forSession(revision, () => verifyAuthEmailCode(email, code));
                        assertLoginIntent();
                        applySession(session, undefined, true);
                    });
                },

                updateUser: (user) => {
                    assertCurrentSession(sessionRevision);
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
                        const revision = sessionRevision;
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
                            if (revision !== sessionRevision) return;
                            if (migrationUnavailable(error)) clearSession(false);
                            else set({ isSessionReady: true, sessionRestorePending: true });
                        }
                    })().finally(() => {
                        initializationPromise = null;
                    });
                    return initializationPromise;
                },

                runAuthenticated: async <Result,>(operation: AuthenticatedOperation<Result>) => {
                    let revision = sessionRevision;
                    let token = get().token;
                    if (!token) {
                        if (!sessionV2Enabled) throw new ApiError('Authentication required', 401);
                        token = (await refreshWithCrossTabLock(null)).token;
                        revision = sessionRevision;
                    }
                    assertCurrentSession(revision);
                    try {
                        return await forSession(revision, () => operation(token!));
                    } catch (error) {
                        if (!sessionV2Enabled || !unauthorized(error)) throw error;
                    }

                    try {
                        const refreshed = await refreshWithCrossTabLock(token);
                        assertCurrentSession(revision);
                        return await forSession(revision, () => operation(refreshed.token));
                    } catch (error) {
                        assertCurrentSession(revision);
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

                acceptRemoteSession: (session, generation, accountEpoch) => {
                    applySession(session, generation, false, accountEpoch);
                },

                acceptRemoteLogout: (pending) => {
                    if (!pending && !get().isAuthenticated && get().logoutPending) {
                        set({ logoutPending: false });
                    } else clearSession(pending);
                },
            };
        },
        {
            name: 'auth-storage',
            storage: createBrowserStateStorage<PersistedAuthState>(browserLocalStorage),
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
