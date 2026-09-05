import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizeTextDecoration } from './textDecoration.ts';
import { buildConstructorCustomization, getCustomDecorationsFromCustomization, getPlacedItemsFromCustomization, getHardwareScaleLimits } from './constructor.ts';

test('text inputs bound size and multiline content without treating markup as HTML', () => {
    const input = normalizeTextDecoration({ content: '  Привет <script>\r\nМир  ', fontId: 'unknown', fontSize: 999, color: 'red' });
    assert.deepEqual(input, { content: 'Привет <script>\nМир', fontId: 'manrope', fontSize: 120, color: '#181818' });
    assert.equal(normalizeTextDecoration({ ...input, content: 'a\n'.repeat(20) }).content.split('\n').length, 6);
});

test('text remains editable with exact geometry after a draft/cart JSON round trip on both views', () => {
    const text = { content: 'Моя коллекция\n2026', fontId: 'inter', fontSize: 48, color: '#123456' };
    const hardware = { id: 'custom_1', categoryId: 'prints', name: text.content, text, src: 'data:image/png;base64,preview', defaultWidth: 243, defaultHeight: 137, price: 80, isCustom: true, minSizeMm: 10, maxSizeMm: 600 };
    const placed = { uid: 'item_1', variantId: hardware.id, x: 213, y: 357, scale: 0.64, rotation: 35 };
    const snapshot = buildConstructorCustomization({ selectedModel: { id: 'product_1', name: 'Hoodie', src: '/front.png', price: 5000 }, selectedSize: 'M', selectedFit: null, garmentDimensions: { widthCm: 68, heightCm: 78 }, placedItemsByView: { front: [placed], back: [{ ...placed, uid: 'item_2', rotation: -10 }] }, hardwareMap: { [hardware.id]: hardware }, frontImage: '/front.png', backImage: '/back.png', totalPrice: 5160, comment: '' });
    const restored = JSON.parse(JSON.stringify(snapshot));
    const variants = getCustomDecorationsFromCustomization(restored);
    assert.equal(variants.length, 1);
    assert.deepEqual(variants[0].text, text);
    assert.equal(variants[0].defaultWidth, 243);
    assert.equal(variants[0].defaultHeight, 137);
    assert.equal(variants[0].src, hardware.src);
    assert.equal(getPlacedItemsFromCustomization(restored).back[0].rotation, -10);
    assert.equal(getPlacedItemsFromCustomization(restored).front[0].scale, 0.64);
    assert.ok(getHardwareScaleLimits(placed, hardware).min < 1);
});
