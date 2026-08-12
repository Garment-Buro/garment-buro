import assert from 'node:assert/strict';
import test from 'node:test';

import {
    formatCartPrice,
    getCartActionTotals,
    getCartItemDetailsRows,
    getCartPanelPresentation,
    getPreferredCartItem,
} from './cartAction.ts';

const item = { id: 'one', product_id: 1, title: 'Платье', price: 1000, image: '', size: 'M', color: 'Белый', quantity: 2 };

test('cart action totals and preferred item keep current cart behavior', () => {
    assert.deepEqual(getCartActionTotals([item], 'courier', { value: 'first-order', label: 'Первый заказ', amount: '10%' }), {
        totalQuantity: 2, productsTotal: 2000, deliveryPrice: 547, discount: 540, grandTotal: 2007,
    });
    assert.equal(getPreferredCartItem([item], null, 'one', true), item);
    assert.equal(formatCartPrice(1234), '1 234 ₽');
});

test('cart details collapse duplicate decorations into count rows', () => {
    const customized = {
        ...item,
        customization: {
            decorations: [{ name: 'Пуговица' }, { name: 'Пуговица' }, { name: 'Молния' }],
        },
    };
    assert.deepEqual(getCartItemDetailsRows(customized), [
        { name: 'Пуговица', count: 2 },
        { name: 'Молния', count: 1 },
    ]);
});

test('cart panel presentation derives drag height and reveal progress', () => {
    const collapsed = getCartPanelPresentation({
        collapsedPanelHeight: 50, expandedPanelHeight: 500, dragOffset: 0,
        dragStartedExpanded: false, isExpanded: false, collapsedVariant: 'glass-compact',
    });
    assert.equal(collapsed.panelDragHeight, undefined);
    assert.equal(collapsed.isCompactCollapsedPresentation, true);
    const dragged = getCartPanelPresentation({
        collapsedPanelHeight: 50, expandedPanelHeight: 500, dragOffset: -100,
        dragStartedExpanded: false, isExpanded: false, collapsedVariant: 'glass-compact',
    });
    assert.equal(dragged.panelDragHeight, '150px');
    assert.ok(dragged.expansionProgress > 0);
});

