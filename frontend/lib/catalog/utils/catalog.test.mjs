import assert from 'node:assert/strict';
import test from 'node:test';

import {
    createCatalogSectionUpdate,
    getOrderedCatalogProducts,
    parseCatalogMediaList,
    selectCatalogProducts,
    splitProductTitle,
} from './catalog.ts';

const products = [
    { id: 1, title: 'First', price: 10 },
    { id: 2, title: 'Second', price: 20 },
    { id: 3, title: 'Third', price: 30 },
];

test('catalog selection keeps configured order and legacy fallbacks', () => {
    assert.deepEqual(selectCatalogProducts(products, [2, 99, 1]).map(product => product.id), [2, 1, 1]);
});

test('mobile catalog keeps curated products first and removes duplicates', () => {
    assert.deepEqual(
        getOrderedCatalogProducts(products, [[products[2], products[0]], [products[2]]]).map(product => product.id),
        [3, 1, 2],
    );
});

test('catalog title and editor updates are computed outside components', () => {
    assert.deepEqual(splitProductTitle('Jacket "Wave"'), ['Jacket ', '"Wave"']);
    assert.deepEqual(splitProductTitle('Jacket'), ['Jacket']);
    assert.deepEqual(parseCatalogMediaList(' first.jpg, /second.jpg '), ['first.jpg', '/second.jpg']);
    assert.deepEqual(
        createCatalogSectionUpdate({
            logo_video_url: '',
            hero_products: [1, 2],
            showroom1_products: [3],
            showroom2_products: [],
            links: {},
        }, 'hero', 1, 7),
        { hero_products: [1, 7] },
    );
});
