import assert from 'node:assert/strict';
import test from 'node:test';

import {
    formatOrderPrice,
    getOrderStatusClassName,
    getOrderStatusLabel,
} from './orderFormatting.ts';

test('order statuses expose reusable labels and visual variants', () => {
    assert.equal(getOrderStatusLabel('new'), 'Новый');
    assert.equal(getOrderStatusLabel('custom'), 'custom');
    assert.equal(getOrderStatusClassName('completed'), 'bg-green-100 text-green-800');
    assert.equal(getOrderStatusClassName('processing'), 'bg-gray-100 text-gray-800');
});

test('order prices preserve the Russian currency presentation', () => {
    assert.equal(formatOrderPrice(12500), '12 500 ₽');
});
