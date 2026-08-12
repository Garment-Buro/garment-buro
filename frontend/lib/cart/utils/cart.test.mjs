import assert from 'node:assert/strict';
import test from 'node:test';

import {
    getActiveCartItemId,
    getCartItemsTotal,
    normalizeCartItem,
    normalizeCartItems,
} from './cart.ts';

test('normalizeCartItem supplies stable primitives and a fallback id', () => {
    assert.deepEqual(normalizeCartItem({ product_id: 12, quantity: 0 }), {
        id: '12__',
        product_id: 12,
        title: '',
        price: 0,
        image: '',
        size: '',
        color: '',
        quantity: 1,
    });
    assert.deepEqual(normalizeCartItems([]), []);
});

test('cart selectors choose a valid preferred item and calculate totals', () => {
    const items = [
        normalizeCartItem({ id: 'first', product_id: 1, price: 100, quantity: 2 }),
        normalizeCartItem({ id: 'last', product_id: 2, price: 50, quantity: 1 }),
    ];
    assert.equal(getActiveCartItemId(items, 'first'), 'first');
    assert.equal(getActiveCartItemId(items, 'missing'), 'last');
    assert.equal(getCartItemsTotal(items), 250);
});

