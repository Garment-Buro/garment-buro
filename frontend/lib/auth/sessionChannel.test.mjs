import assert from 'node:assert/strict';
import test from 'node:test';
import { authSessionChannel, withAuthRefreshLock } from './sessionChannel.ts';

test('cookie mutations never start when the browser cannot coordinate tabs', async () => {
    const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: {} });
    let started = false;
    try {
        await assert.rejects(withAuthRefreshLock(async () => { started = true; }), /coordination unavailable/);
        assert.equal(started, false);
    } finally {
        if (descriptor) Object.defineProperty(globalThis, 'navigator', descriptor);
        else delete globalThis.navigator;
    }
});

test('cookie mutations wait for the previous response and release the lock after failures', async () => {
    let release;
    const pending = new Promise(resolve => { release = resolve; });
    const order = [];
    const first = withAuthRefreshLock(async () => {
        order.push('first-start');
        await pending;
        order.push('first-response');
        throw new Error('Offline');
    });
    const rejected = assert.rejects(first, /Offline/);
    const second = withAuthRefreshLock(async () => { order.push('second-start'); return 'signed-in'; });
    release();
    await rejected;
    assert.equal(await second, 'signed-in');
    assert.deepEqual(order, ['first-start', 'first-response', 'second-start']);
});

test('cookie mutations do not start when real shared storage is denied, full or cannot be read back', async () => {
    const previous = globalThis.window;
    const denied = () => { throw new DOMException('Denied', 'SecurityError'); };
    try {
        for (const localStorage of [null, { setItem: denied }, { setItem() {}, getItem: denied }, { setItem() {}, getItem() { return null; }, removeItem() {} }]) {
            globalThis.window = localStorage ? { localStorage } : Object.defineProperty({}, 'localStorage', { get: denied });
            let calls = 0;
            await assert.rejects(withAuthRefreshLock(async () => { calls++; }), /Для входа разрешите хранение/);
            assert.equal(calls, 0);
        }
    } finally { if (previous === undefined) delete globalThis.window; else globalThis.window = previous; }
});

test('delayed publications cannot replace the latest cross-tab login or log it out', () => {
    const oldWindow = globalThis.window, oldChannel = globalThis.BroadcastChannel;
    const storage = new Map(), publications = [], received = [];
    let deliver;
    globalThis.window = { localStorage: {
        getItem: key => storage.get(key) ?? null,
        setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key),
    } };
    globalThis.BroadcastChannel = class {
        addEventListener(_event, listener) { deliver = data => listener({ data }); }
        postMessage(message) { publications.push(message); }
    };
    const unsubscribe = authSessionChannel.subscribe(message => received.push(message));
    try {
        const a = { token: 'a', user: { id: 1 } }, b = { token: 'b', user: { id: 2 } };
        authSessionChannel.publishSession(a, 'login-a');
        authSessionChannel.publishLogout(true);
        authSessionChannel.publishLogout(false);
        authSessionChannel.publishSession(b, 'login-b');
        publications.forEach(deliver);
        assert.equal(received.length, 1);
        assert.equal(received[0].session.user.id, 2);
        assert.equal(received[0].accountEpoch, 'login-b');
        const before = publications.length;
        const denied = () => { throw new DOMException('Fixture denied', 'SecurityError'); };
        globalThis.window.localStorage = { getItem: denied, setItem: denied, removeItem: denied };
        assert.doesNotThrow(() => authSessionChannel.publishLogout(true));
        assert.equal(publications.length, before, 'a failed shared logout marker is not broadcast as completed');
        assert.equal(authSessionChannel.getSharedGeneration(), null);
        assert.equal(authSessionChannel.getSharedAccountEpoch(), null);
        assert.throws(() => authSessionChannel.publishSession(a, 'unpublished-login'), /Разрешите хранение/);
        deliver(publications.at(-1));
        assert.equal(received.length, 1, 'unreadable shared markers cannot authorize a delayed broadcast');
    } finally {
        unsubscribe(); globalThis.window = oldWindow; globalThis.BroadcastChannel = oldChannel;
    }
});
