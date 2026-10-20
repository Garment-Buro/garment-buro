import assert from 'node:assert/strict';
import test from 'node:test';
import * as constructor from './constructor.ts';
import { getNextDecorationDropPosition } from './interaction.ts';

const saved = {
    activeView: 'back', canvasPixelSize: { width: 1000, height: 900 },
    modelBounds: { x: 150, y: 85, width: 600, height: 700 },
    customization: {
        kind: 'constructor', selectedSize: 'M', modelImages: { front: '/front.webp', back: '/back.webp' },
        canvas: { widthCm: 100, heightCm: 75 }, garment: { widthCm: 60, heightCm: 70 },
        decorations: [{ uid: 'item_1', variantId: 'custom_1', view: 'back', name: 'Принт', price: 80,
            image: '/signed.webp', widthCm: 12, heightCm: 5, x: 330, y: 470, scale: 1, rotation: 15 }],
        totalPrice: 1080,
    },
};
const product = { id: 17, title: 'Новые размеры товара', price: 1000,
    variants: [{ id: 1, size: 'M', color: 'black', stock_quantity: 1, width_cm: 78, height_cm: 92 }] };

test('reopening after catalog dimensions change preserves saved geometry and decoration size on the next save', () => {
    const geometry = constructor.resolveConstructorGeometry(product, 'M', saved);
    assert.deepEqual(geometry.modelBounds, { x: 150, y: 85, width: 600, height: 700 });
    assert.deepEqual(geometry.canvasPixelSize, { width: 1000, height: 900 });
    const decorations = constructor.getCustomDecorationsFromCustomization(saved.customization, geometry.pixelsPerCm);
    const customization = constructor.buildConstructorCustomization({
        selectedModel: { id: 'product_17', name: product.title, src: '/front.webp', price: 1000 },
        selectedSize: 'M', selectedFit: null, garmentDimensions: geometry.garment,
        placedItemsByView: constructor.getPlacedItemsFromCustomization(saved.customization),
        hardwareMap: Object.fromEntries(decorations.map(x => [x.id, x])),
        frontImage: '/front.webp', backImage: '/back.webp', totalPrice: 1080, comment: '', geometry,
    });
    assert.deepEqual(customization.canvas, { widthCm: 100, heightCm: 75 });
    assert.deepEqual(customization.garment, { widthCm: 60, heightCm: 70 });
    assert.equal(customization.decorations[0].widthCm, 12);
    assert.equal(customization.decorations[0].heightCm, 5);
    assert.equal(customization.decorations[0].x, 330);
    assert.equal(customization.decorations[0].y, 470);
    assert.equal(customization.decorations[0].originalWidth, 120);
    assert.equal(customization.decorations[0].originalHeight, 60);
});

test('an explicit size change recalculates bounds within the existing canvas coordinate system', () => {
    const changed = { ...product, variants: [{ ...product.variants[0], size: 'L', width_cm: 70, height_cm: 60 }] };
    const geometry = constructor.resolveConstructorGeometry(changed, 'L', saved);
    assert.deepEqual(geometry.canvasPixelSize, { width: 1000, height: 900 });
    assert.deepEqual(geometry.canvas, { widthCm: 100, heightCm: 75 });
    assert.deepEqual(geometry.garment, { widthCm: 70, heightCm: 60 });
    assert.deepEqual(geometry.modelBounds, { x: 150, y: 90, width: 700, height: 720 });
});

test('new decorations respect both dimensions of a restored rectangular canvas', () => {
    assert.deepEqual(getNextDecorationDropPosition({
        centerPoint: { x: 990, y: 950 }, existingItems: [], canvasSize: { width: 1000, height: 900 },
    }), { x: 990, y: 900 });
});

test('human height is not garment length and the selected color supplies physical length', () => {
    const colored = { ...product, variants: [...product.variants,
        { ...product.variants[0], id: 2, color: 'green', height_cm: 65 }] };
    const fit = constructor.createDefaultFit('M');
    const geometry = constructor.resolveConstructorGeometry(colored, 'M', null, fit, 'green');
    const taller = constructor.resolveConstructorGeometry(colored, 'M', null, { ...fit, lengthCm: 188 }, 'green');
    assert.equal(geometry.garment.heightCm, 65);
    assert.deepEqual(taller.modelBounds, geometry.modelBounds);
    const customization = constructor.buildConstructorCustomization({
        selectedModel: { id: 'product_17', name: product.title, src: '/front.webp', price: 1000 },
        selectedSize: 'M', selectedFit: { ...fit, lengthCm: 188 }, garmentDimensions: geometry.garment,
        placedItemsByView: { front: [], back: [] }, hardwareMap: {},
        frontImage: '/front.webp', backImage: '/back.webp', totalPrice: 1000, comment: '',
    });
    assert.equal(customization.fit.lengthCm, 188);
    assert.equal(customization.garment.heightCm, 65);
});

test('changing human height on a saved project preserves its coordinate system and physical measurements', () => {
    const fit = constructor.createDefaultFit('M', saved.customization.garment);
    const withFit = { ...saved, customization: { ...saved.customization, fit } };
    const geometry = constructor.resolveConstructorGeometry(product, 'M', withFit, { ...fit, lengthCm: 188 });
    assert.deepEqual(geometry.modelBounds, saved.modelBounds);
    assert.deepEqual(geometry.garment, saved.customization.garment);
});

test('a garment length cannot set the default human height, even when its number fits the height range', () => {
    assert.equal(constructor.createDefaultFit('M', { widthCm: 80, heightCm: 185 }).lengthCm, 176);
});

test('cart edit roundtrip preserves rectangular canvas, model alignment and decoration size after a catalog change', () => {
    const geometry = constructor.resolveConstructorGeometry(product, 'M', saved);
    const hardware = constructor.getCustomDecorationsFromCustomization(saved.customization, geometry.pixelsPerCm);
    const customization = constructor.buildConstructorCustomization({
        selectedModel: { id: 'product_17', name: product.title, src: '/front.webp', price: 1000 },
        selectedSize: 'M', selectedFit: null, garmentDimensions: geometry.garment,
        placedItemsByView: constructor.getPlacedItemsFromCustomization(saved.customization),
        hardwareMap: Object.fromEntries(hardware.map(item => [item.id, item])),
        frontImage: '/front.webp', backImage: '/back.webp', totalPrice: 1080, comment: '', geometry,
    });
    const restored = constructor.getConstructorDraftFromCartItem({ customization, image: '/back.webp' });
    assert.deepEqual(restored.canvasPixelSize, saved.canvasPixelSize);
    assert.deepEqual(restored.modelBounds, saved.modelBounds);
    assert.equal(restored.activeView, 'back');
    const edited = constructor.resolveConstructorGeometry(product, 'M', restored);
    assert.deepEqual(edited, geometry);
    const restoredHardware = constructor.getCustomDecorationsFromCustomization(customization, edited.pixelsPerCm);
    const decoration = restoredHardware[0];
    assert.equal(constructor.getItemSizeCm({ scale: 1 }, decoration, edited.pixelsPerCm).widthCm, 12);
    assert.equal(constructor.getItemSizeCm({ scale: 1 }, decoration, edited.pixelsPerCm).heightCm, 5);
});

test('legacy cart uses its saved physical garment and canvas, without trusting a malformed pixel mapping', () => {
    const customization = { ...saved.customization, geometry: { canvasPixelSize: { width: 0, height: 900 }, modelBounds: saved.modelBounds } };
    const restored = constructor.getConstructorDraftFromCartItem({ customization, image: '/front.webp' });
    assert.deepEqual(restored.canvasPixelSize, { width: 800, height: 800 });
    const geometry = constructor.resolveConstructorGeometry(product, 'M', restored);
    assert.deepEqual(geometry.garment, { widthCm: 60, heightCm: 70 });
    assert.deepEqual(geometry.canvas, { widthCm: 100, heightCm: 75 });
    assert.deepEqual(geometry.modelBounds, { x: 160, y: (800 - 70 * (800 / 75)) / 2, width: 480, height: 70 * (800 / 75) });
    assert.equal(constructor.getConstructorDraftFromCartItem({}), null);
});

test('a width adjustment keeps saved garment length, and an explicit color change keeps the canvas coordinate system', () => {
    const fit = { ...constructor.createDefaultFit('M'), widthCm: 60 };
    const restored = { ...saved, customization: { ...saved.customization, fit, selectedColor: 'green' } };
    const wider = constructor.resolveConstructorGeometry(product, 'M', restored, { ...fit, widthCm: 70 }, 'green');
    assert.deepEqual(wider.garment, { widthCm: 70, heightCm: 70 });
    const otherColor = constructor.resolveConstructorGeometry(product, 'M', restored, fit, 'black');
    assert.deepEqual(otherColor.canvasPixelSize, saved.canvasPixelSize);
    assert.deepEqual(otherColor.canvas, saved.customization.canvas);
    assert.deepEqual(otherColor.garment, { widthCm: 60, heightCm: 92 });
    assert.notDeepEqual(otherColor.modelBounds, saved.modelBounds);
});
