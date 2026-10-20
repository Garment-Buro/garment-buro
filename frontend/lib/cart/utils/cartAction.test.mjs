import assert from 'node:assert/strict';
import test from 'node:test';

import {
    formatCartPrice,
    getCartItemDetailsRows,
    getCartPanelPresentation,
    getPreferredCartItem,
} from './cartAction.ts';

const item = { id: 'one', product_id: 1, title: 'Платье', price: 1000, image: '', size: 'M', color: 'Белый', quantity: 2 };

test('cart action chooses the preferred item and formats the displayed price', () => {
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
        dragStartedExpanded: false, isExpanded: false,
    });
    assert.equal(collapsed.panelDragHeight, undefined);
    assert.equal(collapsed.isCompactCollapsedPresentation, true);
    const dragged = getCartPanelPresentation({
        collapsedPanelHeight: 50, expandedPanelHeight: 500, dragOffset: -100,
        dragStartedExpanded: false, isExpanded: false,
    });
    assert.equal(dragged.panelDragHeight, '150px');
    assert.ok(dragged.expansionProgress > 0);
});

for (const collapsedVariant of ['glass-compact', 'liquid-v2']) {
    const presentation = (overrides = {}) => getCartPanelPresentation({
        collapsedPanelHeight: collapsedVariant === 'liquid-v2' ? 45 : 50,
        expandedPanelHeight: 500,
        dragOffset: 0,
        dragStartedExpanded: false,
        isExpanded: false,
        ...overrides,
    });

    test(`${collapsedVariant} reveals checkout only as the panel expands`, () => {
        const collapsed = presentation();
        assert.equal(collapsed.expansionProgress, 0);
        assert.equal(collapsed.expandedSurfaceRevealProgress, 0);
        assert.equal(collapsed.footerRevealProgress, 0);
        assert.equal(collapsed.guestAuthRevealProgress, 0);
        assert.equal(collapsed.overlayRevealProgress, 0);
        assert.equal(collapsed.collapsedContentProgress, 1);
        assert.equal(collapsed.isPanelExpandedPresentation, false);
        assert.equal(collapsed.isCompactCollapsedPresentation, true);

        const expanded = presentation({ isExpanded: true });
        assert.equal(expanded.expansionProgress, 1);
        assert.equal(expanded.expandedSurfaceRevealProgress, 1);
        assert.equal(expanded.footerRevealProgress, 1);
        assert.equal(expanded.guestAuthRevealProgress, 1);
        assert.equal(expanded.overlayRevealProgress, 1);
        assert.equal(expanded.expandedContentProgress, 1);
        assert.equal(expanded.isPanelExpandedPresentation, true);
        assert.equal(expanded.isCompactCollapsedPresentation, false);
    });

    test(`${collapsedVariant} shares the same reveal state in either drag direction`, () => {
        const range = 500 - (collapsedVariant === 'liquid-v2' ? 45 : 50);
        const opening = presentation({ dragOffset: -range / 2 });
        const closing = presentation({ dragOffset: range / 2, dragStartedExpanded: true, isExpanded: true });
        assert.deepEqual(opening, closing);
        assert.equal(opening.expansionProgress, 0.5);
        assert.ok(Math.abs(opening.footerRevealProgress - 11 / 21) < 1e-12);
        assert.ok(Math.abs(opening.expandedSurfaceRevealProgress - 7 / 12) < 1e-12);
        assert.equal(opening.isCompactCollapsedPresentation, false);
        assert.equal(opening.isPanelExpandedPresentation, true);
    });

    test(`${collapsedVariant} clamps dragging to the supported panel bounds`, () => {
        const opening = presentation({ dragOffset: -1000 });
        assert.equal(opening.panelDragHeight, '500px');
        assert.equal(opening.expansionProgress, 1);
        const closing = presentation({ dragOffset: 1000, dragStartedExpanded: true, isExpanded: true });
        assert.equal(closing.panelDragHeight, collapsedVariant === 'liquid-v2' ? '45px' : '50px');
        assert.equal(closing.expansionProgress, 0);
        assert.equal(closing.footerRevealProgress, 0);
    });
}

