import assert from 'node:assert/strict';
import test from 'node:test';
import { createDefaultFit, getProductSizeOptions } from './utils/constructor.ts';
import { constructorCartPayload, constructorColorOptions, constructorSelectionStock, initialConstructorSelection,
    restoreConstructorSelection, selectConstructorSize } from './selection.ts';

const product = { id: 1, title: 'Real model', price: 100, sizes: ['XS','M','L','XXL'], variants: [
    { id: 1, size: 'M', color: 'black', stock_quantity: 0 },
    { id: 2, size: 'M', color: 'green', stock_quantity: 2 },
    { id: 3, size: 'L', color: 'black', stock_quantity: 1 },
] };

test('constructor never invents sizes or availability outside catalog variants', () => {
    const options = getProductSizeOptions(product);
    assert.deepEqual(options.map(x => x.size), ['M', 'L']);
    assert.equal(options[0].stock, 2);
    assert.deepEqual(getProductSizeOptions(null), []);
});

test('base products use only their declared sizes and actual product stock', () => {
    assert.deepEqual(getProductSizeOptions({ id: 1, title: 'Base', price: 100, sizes: ['42','44'], stock_quantity: 0 }).map(x => [x.size, x.stock]), [['42', 0], ['44', 0]]);
    assert.deepEqual(getProductSizeOptions({ id: 1, title: 'One size', price: 100, stock_quantity: 3 }).map(x => [x.size, x.stock]), [['', 3]]);
    assert.equal(createDefaultFit('').selectedSize, '');
});

test('default and explicit size changes select real available colors', () => {
    assert.deepEqual(initialConstructorSelection(product), { size: 'M', color: 'green' });
    assert.deepEqual(selectConstructorSize(product, 'L', 'green'), { size: 'L', color: 'black' });
    assert.deepEqual(constructorColorOptions(product, 'M'), [{ color: 'black', stock: 0 }, { color: 'green', stock: 2 }]);
    assert.equal(constructorSelectionStock(product, { size: 'M', color: 'black' }), 0);
});

test('restoration preserves unavailable selections and never silently substitutes a color', () => {
    assert.deepEqual(restoreConstructorSelection(product, 'M'), { size: 'M', color: null });
    assert.deepEqual(restoreConstructorSelection(product, 'L'), { size: 'L', color: 'black' });
    const historical = restoreConstructorSelection(product, 'XS', 'custom-123');
    assert.deepEqual(historical, { size: 'XS', color: 'custom-123' });
    assert.equal(constructorSelectionStock(product, historical), 0);
});

test('duplicate size/color variants are unavailable rather than arbitrarily choosing a SKU', () => {
    const duplicate = { ...product, variants: [product.variants[1], { ...product.variants[1], id: 8 }] };
    assert.equal(constructorSelectionStock(duplicate, { size: 'M', color: 'green' }), 0);
    assert.equal(initialConstructorSelection(duplicate).size, 'M');
});

test('cart payload carries literal catalog size/color and preserves design; stale selection cannot be purchased', () => {
    const design = { kind: 'constructor', selectedSize: 'M', selectedColor: 'old', totalPrice: 180,
        modelImages: { front: '/green-front.webp', back: '/green-back.webp' }, decorations: [{ uid: 'image', scale: 1, price: 80 }],
        garment: { widthCm: 60, heightCm: 75 }, canvas: { widthCm: 80, heightCm: 80 } };
    const payload = constructorCartPayload(product, { size: 'M', color: 'green' }, design, 'back');
    assert.equal(payload.color, 'green');
    assert.equal(payload.size, 'M');
    assert.equal(payload.image, '/green-back.webp');
    assert.equal(payload.customization.selectedColor, 'green');
    assert.equal(payload.customization.decorations, design.decorations);
    assert.equal(design.selectedColor, 'old');
    assert.equal(constructorCartPayload(product, { size: 'M', color: 'custom-123' }, design, 'front'), null);
    assert.equal(constructorCartPayload(product, { size: 'M', color: null }, design, 'front'), null);
    assert.equal(constructorSelectionStock({ ...product, variants: [{ id: 1, size: null, color: null, stock_quantity: 1 }] }, { size: '', color: '' }), 1);
});
