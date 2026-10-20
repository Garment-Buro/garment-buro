'use client';

import { create } from 'zustand';
import { ApiError, requestJson, requestReadJson } from '@/lib/api/http';
import type { Employee } from '@/lib/production/types';
import {
    observeProductionSession, publishProductionSession, readProductionSession,
    sameProductionSession, withProductionCookieLock, type ProductionSessionMarker,
} from '@/lib/production/sessionCoordination';

type ProductionAuth = {
    user: Employee | null;
    sessionEpoch: string | null;
    isSessionReady: boolean;
    isAuthenticated: boolean;
    error: string;
    initialize: () => Promise<void>;
    login: (code: string) => Promise<void>;
    logout: () => Promise<void>;
    runAuthenticated: <T>(operation: (token: string) => Promise<T>) => Promise<T>;
};
const signedOut = (error = '') => ({
    user: null, sessionEpoch: null, isSessionReady: true, isAuthenticated: false, error,
});
const revoked = () => new DOMException('Сессия изменилась. Войдите снова.', 'AbortError');
const isUnauthorized = (error: unknown) => error instanceof ApiError && error.status === 401;

export const useProductionAuthStore = create<ProductionAuth>((set, get) => {
    let revision = 0;
    let observed: ProductionSessionMarker | null = null;
    let observing = false;
    let initial: { revision: number; promise: Promise<void> } | null = null;
    const publish = (marker: ProductionSessionMarker) => {
        publishProductionSession(marker);
        observed = marker;
    };
    const matches = (marker: ProductionSessionMarker | null, expectedRevision: number) => {
        if (revision !== expectedRevision) return false;
        try { return sameProductionSession(readProductionSession(), marker); }
        catch { return false; }
    };
    const reconcile = () => {
        let shared: ProductionSessionMarker | null;
        try { shared = readProductionSession(); }
        catch (error) {
            revision++;
            set(signedOut(error instanceof Error ? error.message : 'Не удалось проверить сессию.'));
            return;
        }
        if (sameProductionSession(shared, observed)) return;
        revision++;
        observed = shared;
        set(signedOut());
        if (shared?.phase === 'active') void get().initialize();
    };
    const connect = () => {
        if (observing || typeof window === 'undefined') return;
        observing = true;
        observeProductionSession(reconcile);
    };
    const begin = () => {
        connect();
        const current = ++revision;
        set(signedOut());
        const marker: ProductionSessionMarker = { epoch: crypto.randomUUID(), phase: 'pending' };
        publish(marker);
        return { current, marker };
    };
    const currentAccount = (epoch: string | null, id: number | undefined) => {
        const state = get();
        if (!epoch || !state.isAuthenticated || state.sessionEpoch !== epoch || state.user?.id !== id) return false;
        try { return sameProductionSession(readProductionSession(), { epoch, phase: 'active' }); }
        catch { return false; }
    };
    return {
        ...signedOut(), isSessionReady: false,
        initialize: () => {
            connect();
            if (initial?.revision === revision) return initial.promise;
            let marker: ProductionSessionMarker | null;
            try { marker = readProductionSession(); }
            catch (error) {
                set(signedOut(error instanceof Error ? error.message : 'Не удалось проверить сессию.'));
                return Promise.resolve();
            }
            observed = marker;
            if (marker && marker.phase !== 'active') {
                set(signedOut());
                return Promise.resolve();
            }
            const current = revision;
            const promise = withProductionCookieLock(async () => {
                if (!matches(marker, current)) return;
                const user = await requestReadJson<Employee>('/production/me', { cache: 'no-store' });
                if (!matches(marker, current)) return;
                const active: ProductionSessionMarker = marker ?? { epoch: crypto.randomUUID(), phase: 'active' };
                if (!marker) publish(active);
                set({ user, sessionEpoch: active.epoch, isAuthenticated: true, isSessionReady: true, error: '' });
            }).catch(error => {
                if (!matches(marker, current)) return;
                if (isUnauthorized(error)) {
                    revision++;
                    try { publish({ epoch: marker?.epoch ?? crypto.randomUUID(), phase: 'signed_out' }); } catch { /* Local logout still applies. */ }
                }
                set(signedOut(isUnauthorized(error) ? '' : 'Не удалось проверить сессию. Проверьте подключение и настройки браузера.'));
            }).finally(() => { if (initial?.promise === promise) initial = null; });
            initial = { revision: current, promise };
            return promise;
        },
        login: async code => {
            const { current, marker } = begin();
            try {
                await withProductionCookieLock(async () => {
                    if (!matches(marker, current)) throw revoked();
                    // A late Set-Cookie must settle before the next mutation.
                    await requestJson('/production/auth/login', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }),
                    });
                    if (!matches(marker, current)) throw revoked();
                    const user = await requestReadJson<Employee>('/production/me', { cache: 'no-store' });
                    if (!matches(marker, current)) throw revoked();
                    publish({ ...marker, phase: 'active' });
                    set({ user, sessionEpoch: marker.epoch, isAuthenticated: true, isSessionReady: true, error: '' });
                });
            } catch (error) {
                if (!matches(marker, current)) throw revoked();
                try { publish({ ...marker, phase: 'signed_out' }); } catch { /* Keep the local form signed out. */ }
                set(signedOut());
                throw error;
            }
        },
        logout: async () => {
            let intent: ReturnType<typeof begin>;
            try { intent = begin(); }
            catch {
                set(signedOut('Сеанс закрыт на этом устройстве. Сервер не подтвердил выход. Проверьте настройки браузера.'));
                return;
            }
            const { current, marker } = intent;
            let error = '';
            try {
                await withProductionCookieLock(async () => {
                    if (!matches(marker, current)) return;
                    await requestJson('/production/auth/logout', { method: 'POST' });
                });
            } catch (failure) {
                if (!isUnauthorized(failure)) error = 'Сеанс закрыт на этом устройстве. Сервер не подтвердил выход из-за соединения.';
            }
            if (!matches(marker, current)) return;
            try { publish({ ...marker, phase: 'signed_out' }); }
            catch { error = 'Сеанс закрыт на этом устройстве. Не удалось подтвердить выход в других вкладках.'; }
            set(signedOut(error));
        },
        runAuthenticated: async operation => {
            const { sessionEpoch: epoch, user } = get();
            if (!currentAccount(epoch, user?.id)) { reconcile(); throw revoked(); }
            try {
                const result = await operation('');
                if (!currentAccount(epoch, user?.id)) throw revoked();
                return result;
            } catch (error) {
                if (!currentAccount(epoch, user?.id)) throw revoked();
                if (isUnauthorized(error)) {
                    revision++;
                    try { publish({ epoch: epoch!, phase: 'signed_out' }); } catch { /* Local invalidation is mandatory. */ }
                    set(signedOut());
                    throw new ApiError('Сессия завершена. Войдите снова.', 401);
                }
                throw error;
            }
        },
    };
});
