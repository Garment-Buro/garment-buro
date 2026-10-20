import assert from 'node:assert/strict';
import test from 'node:test';

import { getActiveCartItem } from './activeItem.ts';

const first = { id: 'first', product_id: 11, title: 'Первый', price: 100, image: '', size: 'M', color: 'Черный', quantity: 1 };
const last = { id: 'last', product_id: 22, title: 'Последний', price: 200, image: '', size: 'L', color: 'Белый', quantity: 2 };

test('cart selection honors an existing active item even when it is not last', () => {
    assert.equal(getActiveCartItem([first, last], 'first'), first);
});

test('cart selection falls back to the last item after removal or without selection', () => {
    assert.equal(getActiveCartItem([first, last], 'removed'), last);
    assert.equal(getActiveCartItem([first, last], null), last);
});

test('empty cart has no active item', () => {
    assert.equal(getActiveCartItem([], null), undefined);
    assert.equal(getActiveCartItem([], 'removed'), undefined);
});
