import assert from 'node:assert/strict';
import test from 'node:test';

import {
    createAdminProductPayload,
    createEmptyProductVariant,
    mapAdminProductToForm,
} from './productForm.ts';

test('admin API products map into one stable form model', () => {
    const form = mapAdminProductToForm({
        title: 'Футболка',
        price: 4500,
        desktop_card_images: 'one.webp, /two.webp',
        variants: [{ size: 'M', color: 'Чёрный', images: 'front.webp,back.webp' }],
    });

    assert.equal(form.price, '4500');
    assert.deepEqual(form.desktopCardImages, ['/one.webp', '/two.webp']);
    assert.equal(form.variants[0].images, '/front.webp,/back.webp');
});

test('admin form produces the existing backend payload contract', () => {
    const form = mapAdminProductToForm({ title: 'Футболка', price: 4500, stock_quantity: 2 });
    form.variants = [createEmptyProductVariant()];
    const payload = createAdminProductPayload(form);

    assert.equal(payload.price, 4500);
    assert.equal(payload.stock_quantity, 2);
    assert.equal(payload.type, 'normal');
    assert.equal(payload.variants[0].size, 'M');
});
