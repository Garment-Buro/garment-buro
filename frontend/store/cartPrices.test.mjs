import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import * as cartUtils from '../lib/cart/utils/cart.ts';
import * as browserStorage from '../lib/browser/utils/storage.ts';

const require = createRequire(import.meta.url);
const ts = require('typescript');
const { create } = require('zustand');
const { persist, createJSONStorage } = require('zustand/middleware');
const item = { id: 'one', product_id: 7, title: 'Товар', price: 1000, quantity: 2, image: '', size: 'M', color: 'black', customization: { text: 'Сохранить' } };
const prices = [{ id: 'one', productId: 7, price: 1500 }, { id: 'two', productId: 7, price: 1200 }];

function loadCart() {
    const memory = new Map(), timers = new Map(), writes = [];
    const storage = { getItem: key => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, value), removeItem: key => memory.delete(key) };
    const loadedModule = { exports: {} };
    const code = ts.transpileModule(fs.readFileSync(new URL('./cartStore.ts', import.meta.url), 'utf8'), {
        compilerOptions: { module: ts.ModuleKind.CommonJS },
    }).outputText;
    vm.runInNewContext(code, {
        module: loadedModule, exports: loadedModule.exports, window: {crypto: globalThis.crypto}, console,
        setTimeout: callback => { const key = Symbol(); timers.set(key, callback); return key; }, clearTimeout: key => timers.delete(key),
        require: name => {
            if (name === 'zustand') return { create };
            if (name === 'zustand/middleware') return { persist: (fn, options) => persist(fn, { ...options, storage: createJSONStorage(() => storage) }) };
            if (name === '@/lib/cart/utils/cart') return cartUtils;
            if (name === '@/lib/cart/snapshotSync') return require('../lib/cart/snapshotSync.ts');
            if (name === '@/lib/browser/utils/storage') return browserStorage;
            if (name === '@/lib/api/cart') return { getCartSnapshot: async () => ({items:[],revision:null,updated_at_ms:0}), syncCartSnapshot: async (_, data) => { writes.push(data); return {items:data.items,revision:"a".repeat(32),updated_at_ms:0}; } };
            throw new Error(name);
        },
    });
    const store = loadedModule.exports.useCartStore;
    store.setState({ items: [structuredClone(item), { ...structuredClone(item), id: 'two', size: 'L' }], hasHydrated: true, cartId: 'test-cart', isCartOpen: true, activeItemId: 'one' });
    return { store, writes, flush: async () => { for (const callback of [...timers.values()]) await callback(); await store.getState().syncCartToServer({immediate:true}); } };
}

test('confirmed server prices update all cart lines atomically with one sync and retain customization', async () => {
    const { store, writes, flush } = loadCart();
    const before = store.getState().items;
    assert.equal(store.getState().applyCheckoutPrices(before, prices), true);
    const state = store.getState();
    assert.equal(state.items[0].price, 1500);
    assert.equal(state.items[1].price, 1200);
    assert.equal(state.items[0].quantity, 2);
    assert.equal(state.items[0].customization.text, 'Сохранить');
    assert.equal(state.items[1].size, 'L');
    assert.equal(state.isCartOpen, true);
    assert.equal(state.activeItemId, 'one');
    await flush();
    assert.equal(writes.length, 1);
    assert.equal(writes[0].items[0].price, 1500);
});

test('a late price response cannot overwrite cart edits made during the request', () => {
    const { store } = loadCart();
    const before = store.getState().items;
    store.getState().updateQuantity('one', 5);
    assert.equal(store.getState().applyCheckoutPrices(before, prices), false);
    assert.equal(store.getState().items[0].quantity, 5);
    assert.equal(store.getState().items[0].price, 1000);
});

test('partial or mismatched price snapshots cannot partially reprice the cart', () => {
    const { store } = loadCart();
    const before = store.getState().items;
    for (const invalid of [prices.slice(0, 1), [prices[0], prices[0]], [prices[0], { ...prices[1], productId: 99 }]]) {
        assert.equal(store.getState().applyCheckoutPrices(before, invalid), false);
        assert.equal(store.getState().items, before);
    }
});
