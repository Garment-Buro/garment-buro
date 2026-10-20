import { requireWritableStorage } from '../browser/utils/storage.ts';

// Shared metadata contains no credentials or employee data.
export const PRODUCTION_SESSION_KEY = 'gb-production-session-lifetime';
export type ProductionSessionMarker = { epoch: string; phase: 'pending' | 'active' | 'signed_out' };
const unavailable = () => new Error('Для входа разрешите хранение данных браузера и попробуйте снова.');

export function readProductionSession(): ProductionSessionMarker | null {
    try {
        const raw = window.localStorage.getItem(PRODUCTION_SESSION_KEY);
        if (raw === null) return null;
        const value: unknown = JSON.parse(raw);
        if (value && typeof value === 'object' && 'epoch' in value && 'phase' in value
            && typeof value.epoch === 'string' && value.epoch.length > 0 && value.epoch.length <= 80
            && ['pending', 'active', 'signed_out'].includes(String(value.phase)))
            return value as ProductionSessionMarker;
    } catch { /* An unreadable marker cannot authorize a request. */ }
    throw unavailable();
}
export function publishProductionSession(marker: ProductionSessionMarker) {
    requireWritableStorage(() => window.localStorage);
    const raw = JSON.stringify(marker);
    try {
        window.localStorage.setItem(PRODUCTION_SESSION_KEY, raw);
        if (window.localStorage.getItem(PRODUCTION_SESSION_KEY) !== raw) throw unavailable();
    } catch { throw unavailable(); }
}
export const sameProductionSession = (a: ProductionSessionMarker | null, b: ProductionSessionMarker | null) =>
    a?.epoch === b?.epoch && a?.phase === b?.phase;

export async function withProductionCookieLock<T>(operation: () => Promise<T>): Promise<T> {
    if (typeof navigator === 'undefined' || !navigator.locks)
        return Promise.reject(new Error('Этот браузер не поддерживает безопасное согласование входа. Обновите браузер.'));
    return await navigator.locks.request('garment-buro-production-cookie', async () => {
        requireWritableStorage(() => window.localStorage);
        return operation();
    });
}
export function observeProductionSession(reconcile: () => void) {
    const onStorage = (event: StorageEvent) => {
        if (event.key === PRODUCTION_SESSION_KEY || event.key === null) reconcile();
    };
    const onVisible = () => { if (document.visibilityState === 'visible') reconcile(); };
    window.addEventListener('storage', onStorage);
    window.addEventListener('focus', reconcile);
    window.addEventListener('pageshow', reconcile);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
        window.removeEventListener('storage', onStorage);
        window.removeEventListener('focus', reconcile);
        window.removeEventListener('pageshow', reconcile);
        document.removeEventListener('visibilitychange', onVisible);
    };
}
