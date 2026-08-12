import assert from 'node:assert/strict';
import test from 'node:test';

import {
    fillReviewImages,
    getNextProducts,
    getPreferredVariant,
    getProductVariantPresentation,
    getRelatedProductPages,
    localizeProductColor,
    normalizeProductDescription,
} from './product.ts';

const products = Array.from({ length: 8 }, (_, index) => ({
    id: index + 1,
    title: `Product ${index + 1}`,
    price: 100 + index,
}));

test('product helpers preserve variant selection and media fallbacks', () => {
    const product = {
        ...products[0],
        stock_quantity: 4,
        desktop_slider_images: 'desktop-1.jpg,desktop-2.jpg',
        variants: [
            { id: 1, size: 'S', color: 'black', stock_quantity: 0, images: '' },
            { id: 2, size: 'M', color: 'black', stock_quantity: 2, images: 'variant-1.jpg,variant-2.jpg' },
        ],
    };
    assert.equal(getPreferredVariant(product)?.size, 'M');
    const presentation = getProductVariantPresentation(product, 'black', 'M');
    assert.equal(presentation.currentStock, 2);
    assert.deepEqual(presentation.desktopSliderImages, ['variant-1.jpg', 'variant-2.jpg']);
    assert.deepEqual(presentation.colorOptions, [{ label: 'black', hex: '#888888' }]);
});

test('product collections keep existing review and related ordering', () => {
    assert.deepEqual(getNextProducts(products, 8).map(product => product.id), [1, 2]);
    assert.deepEqual(getRelatedProductPages(products).map(page => page.length), [6, 2]);
    assert.deepEqual(fillReviewImages(['one.jpg'], 3), ['one.jpg', '/landing-bg.webp', '/landing-bg.webp']);
});

test('product text helpers preserve display values', () => {
    assert.equal(localizeProductColor('black'), 'Черный');
    assert.equal(localizeProductColor('white'), 'Белый');
    assert.equal(localizeProductColor('blue'), 'blue');
    assert.equal(normalizeProductDescription('first\r\nsecond\u2028third'), 'first\nsecond\nthird');
});
