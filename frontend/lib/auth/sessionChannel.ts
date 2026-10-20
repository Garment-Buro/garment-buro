import type { AuthSessionResponse } from '@/lib/auth/types';
import { requireWritableStorage } from '../browser/utils/storage.ts';

const CHANNEL_NAME = 'garment-buro-auth-session-v2';
const GENERATION_KEY = 'gb-auth-session-generation';
const ACCOUNT_EPOCH_KEY = 'gb-auth-account-epoch';
const LOCK_NAME = 'garment-buro-auth-refresh';

export type AuthSessionChannelMessage =
    | { type: 'session'; generation: string; accountEpoch: string; session: AuthSessionResponse }
    | { type: 'logout'; generation: string; pending: boolean };

type Listener = (message: AuthSessionChannelMessage) => void;

let channel: BroadcastChannel | null = null;
let latestSessionMessage: Extract<AuthSessionChannelMessage, { type: 'session' }> | null = null;
const listeners = new Set<Listener>();

const storage = () => {
    if (typeof window === 'undefined') return null;
    try {
        return window.localStorage;
    } catch {
        return null;
    }
};

const readSharedMarker = (key: string) => {
    try { return storage()?.getItem(key) || null; }
    catch { return null; }
};

const ensureChannel = () => {
    if (channel || typeof BroadcastChannel === 'undefined') return channel;
    channel = new BroadcastChannel(CHANNEL_NAME);
    channel.addEventListener('message', (event: MessageEvent<AuthSessionChannelMessage>) => {
        const message = event.data;
        if (!message || (message.type !== 'session' && message.type !== 'logout')) return;
        // Hidden tabs may receive old events after a newer cookie/session write.
        let sharedGeneration: string | null;
        try {
            const sharedStorage = storage();
            if (!sharedStorage) return;
            sharedGeneration = sharedStorage.getItem(GENERATION_KEY);
        } catch {
            return; // Cannot reconcile account lifetimes without shared markers.
        }
        if (sharedGeneration && message.generation !== sharedGeneration) return;
        if (message.type === 'session') latestSessionMessage = message;
        listeners.forEach(listener => listener(message));
    });
    return channel;
};

const newId = () => {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

export const authSessionChannel = {
    subscribe(listener: Listener) {
        listeners.add(listener);
        ensureChannel();
        return () => listeners.delete(listener);
    },

    publishSession(session: AuthSessionResponse, accountEpoch: string) {
        const generation = newId();
        const message: Extract<AuthSessionChannelMessage, { type: 'session' }> = {
            type: 'session',
            generation,
            accountEpoch,
            session,
        };
        latestSessionMessage = message;
        try {
            const sharedStorage = storage();
            if (!sharedStorage) throw new Error();
            sharedStorage.setItem(ACCOUNT_EPOCH_KEY, accountEpoch);
            sharedStorage.setItem(GENERATION_KEY, generation);
        } catch {
            latestSessionMessage = null;
            throw new Error('Не удалось сохранить состояние входа. Разрешите хранение данных браузера и попробуйте снова.');
        }
        ensureChannel()?.postMessage(message);
        return generation;
    },

    publishLogout(pending: boolean) {
        // Completion belongs to the same logout intent, so a login deliberately
        // queued after that intent remains valid when its HTTP response arrives.
        const generation = !pending && !readSharedMarker(ACCOUNT_EPOCH_KEY)
            ? readSharedMarker(GENERATION_KEY) || newId() : newId();
        latestSessionMessage = null;
        try {
            const sharedStorage = storage();
            if (!sharedStorage) return;
            sharedStorage.setItem(GENERATION_KEY, generation);
            sharedStorage.removeItem(ACCOUNT_EPOCH_KEY);
        } catch {
            return; // Local logout stays pending; never publish a marker other tabs cannot verify.
        }
        ensureChannel()?.postMessage({ type: 'logout', generation, pending });
    },

    getSharedGeneration() {
        return readSharedMarker(GENERATION_KEY);
    },

    getSharedAccountEpoch() {
        return readSharedMarker(ACCOUNT_EPOCH_KEY);
    },

    async waitForSession(generation: string, timeoutMs = 750) {
        if (latestSessionMessage?.generation === generation) {
            return latestSessionMessage;
        }
        return new Promise<Extract<AuthSessionChannelMessage, { type: 'session' }> | null>((resolve) => {
            const timeout = window.setTimeout(() => {
                listeners.delete(listener);
                resolve(null);
            }, timeoutMs);
            const listener: Listener = (message) => {
                if (message.type !== 'session' || message.generation !== generation) return;
                window.clearTimeout(timeout);
                listeners.delete(listener);
                resolve(message);
            };
            listeners.add(listener);
            ensureChannel();
        });
    },
};

export async function withAuthRefreshLock<Result>(
    operation: () => Promise<Result>,
): Promise<Result> {
    if (typeof navigator !== 'undefined' && navigator.locks) {
        return navigator.locks.request(LOCK_NAME, async () => {
            if (typeof window !== 'undefined') requireWritableStorage(() => window.localStorage);
            return operation();
        });
    }
    // A localStorage lease is not atomic across tabs and can expire while a
    // response still carries Set-Cookie. Never run cookie mutations unlocked.
    throw new Error('Authentication coordination unavailable');
}
