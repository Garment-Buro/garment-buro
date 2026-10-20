import assert from 'node:assert/strict';
import test from 'node:test';
import { createStore } from 'zustand/vanilla';
import { persist } from 'zustand/middleware';
import { createOptionalBrowserStorage, createBrowserStateStorage, requireWritableStorage } from './storage.ts';

const memory = () => {
    const values = new Map();
    return { values, getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
};
const denied = () => { throw new DOMException('Fixture denied', 'SecurityError'); };
const full = () => { throw new DOMException('Fixture full', 'QuotaExceededError'); };
const storeWith = storage => createStore(persist(set => ({ count: 0, increment: () => set(state => ({ count: state.count + 1 })) }), {
    name: 'fixture', storage: createBrowserStateStorage(storage), partialize: state => ({ count: state.count }),
}));

test('Zustand keeps its hydration API and live state when the storage getter is denied', () => {
    const storage = createOptionalBrowserStorage(denied), store = storeWith(storage);
    assert.equal(store.persist.hasHydrated(), true);
    store.getState().increment();
    assert.equal(store.getState().count, 1);
    assert.equal(storeWith(storage).getState().count, 1, 'same document can recover its fallback cache');
    assert.equal(storeWith(createOptionalBrowserStorage(denied)).getState().count, 0, 'a new document has no durable cache');
});

test('a failed cache write overrides old disk data until a later successful write', () => {
    const native = memory(); native.setItem('fixture', JSON.stringify({ state: { count: 4 }, version: 0 }));
    let writable = false;
    const storage = createOptionalBrowserStorage(() => ({ ...native, setItem: (...args) => writable ? native.setItem(...args) : full() }));
    const store = storeWith(storage); assert.equal(store.getState().count, 4);
    store.getState().increment();
    assert.equal(storeWith(storage).getState().count, 5);
    assert.equal(JSON.parse(native.getItem('fixture')).state.count, 4);
    writable = true; store.getState().increment();
    assert.equal(storeWith(createOptionalBrowserStorage(() => native)).getState().count, 6);
});

test('a failed removal never resurrects the previous cached value', () => {
    const native = memory(); native.setItem('consent', 'old');
    const storage = createOptionalBrowserStorage(() => ({ ...native, removeItem: denied }));
    storage.removeItem('consent');
    assert.equal(storage.getItem('consent'), null);
    assert.equal(native.getItem('consent'), 'old');
});

test('SSR performs no storage writes and never transfers fallback state to a second request', () => {
    const storage = createOptionalBrowserStorage(() => null);
    const first = storeWith(storage); first.getState().increment();
    assert.equal(storage.getItem('fixture'), null);
    assert.equal(storeWith(storage).getState().count, 0);
});

test('invalid cache JSON and invalid envelopes still complete hydration', () => {
    for (const raw of ['broken JSON', 'null', '[]', '{}', '{"state":{},"version":"2"}']) {
        const native = memory(); native.setItem('fixture', raw);
        const store = storeWith(createOptionalBrowserStorage(() => native));
        assert.equal(store.persist.hasHydrated(), true, raw);
        assert.equal(store.getState().count, 0, raw);
    }
});

test('ordinary storage reloads the cache and observes writes made by another document', () => {
    const native = memory(), storage = createOptionalBrowserStorage(() => native);
    const store = storeWith(storage); store.getState().increment();
    assert.equal(storeWith(createOptionalBrowserStorage(() => native)).getState().count, 1);
    native.setItem('fixture', JSON.stringify({ state: { count: 8 }, version: 0 }));
    assert.equal(storeWith(storage).getState().count, 8);
});

test('auth coordination probes require actual durable storage and clean up only their own marker', () => {
    const native = memory(); native.setItem('unrelated', 'keep');
    requireWritableStorage(() => native);
    assert.deepEqual([...native.values], [['unrelated', 'keep']]);
    for (const resolve of [denied, () => ({ ...native, setItem: full }), () => ({ ...native, getItem: denied }), () => ({ ...native, setItem: () => {} })]) {
        assert.throws(() => requireWritableStorage(resolve), /Для входа разрешите хранение/);
    }
});
