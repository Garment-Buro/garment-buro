import type { AuthSessionResponse } from '@/lib/auth/types';

const CHANNEL_NAME = 'garment-buro-auth-session-v2';
const GENERATION_KEY = 'gb-auth-session-generation';
const LOCK_KEY = 'gb-auth-refresh-lock';
const LOCK_NAME = 'garment-buro-auth-refresh';
const LOCK_TTL_MS = 15_000;
const LOCK_WAIT_MS = 20_000;

export type AuthSessionChannelMessage =
    | { type: 'session'; generation: string; session: AuthSessionResponse }
    | { type: 'logout'; pending: boolean };

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

const ensureChannel = () => {
    if (channel || typeof BroadcastChannel === 'undefined') return channel;
    channel = new BroadcastChannel(CHANNEL_NAME);
    channel.addEventListener('message', (event: MessageEvent<AuthSessionChannelMessage>) => {
        const message = event.data;
        if (!message || (message.type !== 'session' && message.type !== 'logout')) return;
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

    publishSession(session: AuthSessionResponse) {
        const generation = newId();
        const message: Extract<AuthSessionChannelMessage, { type: 'session' }> = {
            type: 'session',
            generation,
            session,
        };
        latestSessionMessage = message;
        storage()?.setItem(GENERATION_KEY, generation);
        ensureChannel()?.postMessage(message);
        return generation;
    },

    publishLogout(pending: boolean) {
        latestSessionMessage = null;
        storage()?.removeItem(GENERATION_KEY);
        ensureChannel()?.postMessage({ type: 'logout', pending });
    },

    getSharedGeneration() {
        return storage()?.getItem(GENERATION_KEY) || null;
    },

    async waitForSession(generation: string, timeoutMs = 750) {
        if (latestSessionMessage?.generation === generation) {
            return latestSessionMessage.session;
        }
        return new Promise<AuthSessionResponse | null>((resolve) => {
            const timeout = window.setTimeout(() => {
                listeners.delete(listener);
                resolve(null);
            }, timeoutMs);
            const listener: Listener = (message) => {
                if (message.type !== 'session' || message.generation !== generation) return;
                window.clearTimeout(timeout);
                listeners.delete(listener);
                resolve(message.session);
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
        return navigator.locks.request(LOCK_NAME, operation);
    }
    const browserStorage = storage();
    if (!browserStorage) return operation();

    const owner = newId();
    const deadline = Date.now() + LOCK_WAIT_MS;
    let acquired = false;
    while (!acquired && Date.now() < deadline) {
        const now = Date.now();
        const current = parseLock(browserStorage.getItem(LOCK_KEY));
        if (!current || current.expiresAt <= now) {
            browserStorage.setItem(
                LOCK_KEY,
                JSON.stringify({ owner, expiresAt: now + LOCK_TTL_MS }),
            );
            acquired = parseLock(browserStorage.getItem(LOCK_KEY))?.owner === owner;
        }
        if (!acquired) await delay(40 + Math.floor(Math.random() * 30));
    }
    if (!acquired) return operation();
    try {
        return await operation();
    } finally {
        if (parseLock(browserStorage.getItem(LOCK_KEY))?.owner === owner) {
            browserStorage.removeItem(LOCK_KEY);
        }
    }
}

const parseLock = (value: string | null): { owner: string; expiresAt: number } | null => {
    if (!value) return null;
    try {
        const parsed = JSON.parse(value) as { owner?: unknown; expiresAt?: unknown };
        if (typeof parsed.owner === 'string' && typeof parsed.expiresAt === 'number') {
            return { owner: parsed.owner, expiresAt: parsed.expiresAt };
        }
    } catch {
        // Treat malformed or externally cleared state as an available lock.
    }
    return null;
};

const delay = (milliseconds: number) => new Promise<void>(resolve => {
    window.setTimeout(resolve, milliseconds);
});
