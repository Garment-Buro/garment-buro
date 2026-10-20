type BrowserStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
type StateValue<State> = { state: State; version?: number };

/** Optional preferences/cache only. Never use this for purchase recovery. */
export function createOptionalBrowserStorage(resolve: () => BrowserStorage | null): BrowserStorage {
    const pending = new Map<string, string | null>();
    return {
        getItem(key) {
            try {
                const storage = resolve();
                if (!storage) return null; // SSR must never read document fallback state.
                if (pending.has(key)) return pending.get(key) ?? null;
                return storage.getItem(key);
            } catch {
                return pending.get(key) ?? null;
            }
        },
        setItem(key, value) {
            try {
                const storage = resolve();
                if (!storage) return;
                storage.setItem(key, value);
                pending.delete(key);
            } catch {
                pending.set(key, value);
            }
        },
        removeItem(key) {
            try {
                const storage = resolve();
                if (!storage) return;
                storage.removeItem(key);
                pending.delete(key);
            } catch {
                // A failed delete must not resurrect an older persisted value.
                pending.set(key, null);
            }
        },
    };
}

export const browserLocalStorage = createOptionalBrowserStorage(
    () => typeof window === 'undefined' ? null : window.localStorage,
);
export const browserSessionStorage = createOptionalBrowserStorage(
    () => typeof window === 'undefined' ? null : window.sessionStorage,
);

/** A malformed browser cache must not prevent Zustand finishing hydration. */
export function createBrowserStateStorage<State>(storage: BrowserStorage) {
    return {
        getItem(key: string): StateValue<State> | null {
            try {
                const raw = storage.getItem(key);
                if (raw === null) return null;
                const value: unknown = JSON.parse(raw);
                if (!value || typeof value !== 'object' || Array.isArray(value) || !('state' in value)) return null;
                if ('version' in value && (!Number.isInteger(value.version) || Number(value.version) < 0)) return null;
                return value as StateValue<State>;
            } catch {
                return null;
            }
        },
        setItem: (key: string, value: StateValue<State>) => storage.setItem(key, JSON.stringify(value)),
        removeItem: (key: string) => storage.removeItem(key),
    };
}

/** Cookie mutations need real shared storage; document fallback is insufficient. */
export function requireWritableStorage(resolve: () => BrowserStorage) {
    let storage: BrowserStorage | undefined;
    let key: string | undefined;
    try {
        storage = resolve();
        const marker = crypto.randomUUID();
        key = `gb-auth-storage-check:${marker}`;
        storage.setItem(key, marker);
        const stored = storage.getItem(key);
        storage.removeItem(key);
        if (stored !== marker || storage.getItem(key) !== null) throw new Error();
    } catch {
        throw new Error('Для входа разрешите хранение данных браузера и попробуйте снова.');
    } finally {
        if (storage && key) {
            try { storage.removeItem(key); } catch { /* Storage may have become unavailable during the probe. */ }
        }
    }
}
