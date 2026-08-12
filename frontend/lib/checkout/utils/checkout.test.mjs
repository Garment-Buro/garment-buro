import assert from 'node:assert/strict';
import test from 'node:test';

import {
    createCdekGoods,
    createCheckoutOrderPayload,
    EMPTY_CHECKOUT_FORM,
    formatRussianPhone,
    getCartItemFitSummary,
    getCheckoutErrors,
} from './checkout.ts';

test('checkout phone and required fields keep their current validation rules', () => {
    assert.equal(formatRussianPhone('89991234567'), '+7 (999) 123-45-67');
    assert.deepEqual(Object.keys(getCheckoutErrors(EMPTY_CHECKOUT_FORM)).sort(), ['agreeOffer', 'agreePolicy', 'deliveryAddress', 'email', 'firstName', 'phone']);
});

test('CDEK goods expand cart quantities and keep a fallback package', () => {
    assert.equal(createCdekGoods([]).length, 1);
    assert.equal(createCdekGoods([{ quantity: 3 }]).length, 3);
});

test('checkout payload and fit summary preserve backend and UI contracts', () => {
    const form = { ...EMPTY_CHECKOUT_FORM, email: 'test@example.com', phone: '+7', firstName: 'Иван', deliveryAddress: 'Москва', agreeOffer: true, agreePolicy: true };
    const payload = createCheckoutOrderPayload({ form, items: [], totalPrice: 1000, deliveryPrice: 250 });
    assert.equal(payload.total_price, 1250);
    assert.equal(payload.delivery_method, 'cdek');
    assert.equal(getCartItemFitSummary({ customization: { fit: { sleeveMode: 'height', lengthCm: 70, widthCm: 55 } } }), 'Посадка: длина 70, ширина 55, рукава под рост');
});
