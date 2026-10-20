import assert from 'node:assert/strict';
import test from 'node:test';

import {
    createCheckoutOrderPayload,
    getCartItemFitSummary,
} from './checkout.ts';

test('purchase payload preserves independent contacts and uses the canonical signed destination', () => {
    const buyer = { name: 'Покупатель', phone: '+79001234567', email: 'buyer@example.test' };
    const recipient = { name: 'Получатель', phone: '+79007654321', email: 'recipient@example.test' };
    const payload = createCheckoutOrderPayload({
        buyer, recipient, items: [{ id: 'line', product_id: 7, price: 1000, quantity: 2 }], paymentMethod: 'card',
        deliveryMethod: 'cdek_pickup',
        quote: { delivery_price: 250, quote_token: 'proof', delivery_city: 'Тверь', delivery_address: 'Советская, 1', cdek_point_code: 'TVR1', currency: 'RUB' },
    });
    assert.deepEqual(payload, {
        buyer, recipient, items: [{ id: 'line', product_id: 7, price: 1000, quantity: 2 }],
        payment_method: 'card', delivery_method: 'cdek_pickup', currency: 'RUB',
        delivery_city: 'Тверь', delivery_address: 'Советская, 1', cdek_point_code: 'TVR1',
        claimed_total_price: 2250, delivery_price: 250, delivery_quote_token: 'proof',
    });
});

test('fit summary describes the chosen sleeve mode', () => {
    assert.equal(getCartItemFitSummary({ customization: { fit: { sleeveMode: 'height', lengthCm: 70, widthCm: 55 } } }), 'Посадка: длина 70, ширина 55, рукава под рост');
});
