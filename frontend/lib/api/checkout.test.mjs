import assert from 'node:assert/strict';
import test from 'node:test';
import { createCheckoutOrder, calculateCdekDelivery, getCheckoutPaymentOptions } from './checkout.ts';
import { createCartActionOrder, getOrderDetails } from './orders.ts';
import { requestJson } from './http.ts';

const TEST_PURCHASE_OPERATION = 'test-purchase-operation';

const payload = {
    buyer: { name: 'Покупатель Тест', phone: '+79001234567', email: 'buyer@example.test' },
    recipient: { name: 'Получатель Тест', phone: '+79007654321', email: 'recipient@example.test' },
    items: [{ id: 'line-7', product_id: 7, price: 1000, quantity: 2 }],
    delivery_method: 'cdek_pickup', delivery_city: 'Тверь', delivery_address: 'Советская, 1',
    cdek_point_code: 'TVR1', delivery_price: 250, delivery_quote_token: 'signed-proof',
    claimed_total_price: 2250, payment_method: 'card', currency: 'RUB',
};

for (const [name, submit] of [['страница', createCheckoutOrder], ['корзина', createCartActionOrder]]) {
    for (const kind of ['customer', 'guest']) {
        test(`${name}: purchase uses one actor, durable operation key and modern body (${kind})`, async t => {
            let captured;
            t.mock.method(globalThis, 'fetch', async (url, init) => {
                captured = { url, init };
                return Response.json({ order_id: 42, payment_url: 'https://payments.example.test/42' });
            });
            const token = kind === 'guest' ? 'g'.repeat(43) : 'access-token';
            const result = await submit(payload, { idempotencyKey: TEST_PURCHASE_OPERATION, actor: { kind, token } });
            const headers = new Headers(captured.init.headers);
            assert.equal(captured.url, '/api/orders');
            assert.equal(headers.get('Idempotency-Key'), TEST_PURCHASE_OPERATION);
            assert.equal(headers.get('Authorization'), kind === 'customer' ? 'Bearer access-token' : null);
            assert.equal(headers.get('X-Order-Access-Token'), kind === 'guest' ? token : null);
            assert.deepEqual(JSON.parse(captured.init.body), payload);
            assert.equal(captured.init.cache, 'no-store');
            assert.equal(result.order_id, 42);
        });
    }
}

test('quote request includes pickup identity or courier address and is cancellable', async t => {
    const calls = [];
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        calls.push({ url, init });
        return Response.json({ delivery_price: 250, quote_token: 'signed-proof', delivery_city: 'Тверь', delivery_address: 'Советская, 1', cdek_point_code: 'TVR1', tariff_code: 136, currency: 'RUB' });
    });
    const signal = new AbortController().signal;
    await calculateCdekDelivery({ city: 'Тверь', delivery_method: 'cdek_pickup', cdek_point_code: 'TVR1', cart_items: [{ product_id: 7, quantity: 2 }] }, signal);
    assert.equal(calls[0].init.signal, signal);
    assert.equal(calls[0].init.cache, 'no-store');
    assert.equal(JSON.parse(calls[0].init.body).cdek_point_code, 'TVR1');
});

test('payment options never offer QR when a hold is required or the policy is malformed', async t => {
    let data = { hold_required: true, payment_methods: ['card', 'qr'] };
    t.mock.method(globalThis, 'fetch', async () => Response.json(data));
    assert.deepEqual(await getCheckoutPaymentOptions(), ['card']);
    data = { hold_required: false, payment_methods: ['card', 'qr'] };
    assert.deepEqual(await getCheckoutPaymentOptions(), ['card', 'qr']);
    data = { payment_methods: ['qr'] };
    await assert.rejects(getCheckoutPaymentOptions(), /оплаты/);
});

test('payment failure retains only safe typed metadata for deliberate retry', async t => {
    t.mock.method(globalThis, 'fetch', async () => Response.json({ detail: {
        code: 'payment_rejected', order_id: 42, email: 'private@example.test', token: 'never-retain',
    } }, { status: 502, headers: { 'X-Request-ID': 'request-1', 'Retry-After': '2' } }));
    await assert.rejects(requestJson('/orders'), error => {
        assert.equal(error.code, 'payment_rejected');
        assert.equal(error.orderId, 42);
        assert.equal(error.retryAfter, 2);
        assert.equal(error.requestId, 'request-1');
        assert.doesNotMatch(JSON.stringify(error), /private|never-retain/);
        return true;
    });
});

test('definite price rejection exposes only bounded authoritative item prices', async t => {
    t.mock.method(globalThis, 'fetch', async () => Response.json({ detail: {
        code: 'checkout_price_changed', currency: 'RUB',
        prices: [{ id: 'line-7', product_id: 7, price: 1500, token: 'never-retain' }],
        email: 'private@example.test',
    } }, { status: 409 }));
    await assert.rejects(createCheckoutOrder(payload, { idempotencyKey: TEST_PURCHASE_OPERATION, actor: { kind: 'guest', token: 'g'.repeat(43) } }), error => {
        assert.deepEqual(error.checkoutPrices, [{ id: 'line-7', productId: 7, price: 1500 }]);
        assert.doesNotMatch(JSON.stringify(error), /private|never-retain/);
        return true;
    });
});

test('invalid or ambiguous price responses cannot alter the cart', async t => {
    let detail;
    let status = 409;
    t.mock.method(globalThis, 'fetch', async () => Response.json({ detail }, { status }));
    for (const prices of [[], [{ id: 'line-7', product_id: 7, price: -1 }], [{ id: 'line-7', product_id: 7, price: '1500' }],
        [{ id: 'line-7', product_id: 7, price: 1.234 }], Array(101).fill({ id: 'line-7', product_id: 7, price: 1500 })]) {
        detail = { code: 'checkout_price_changed', currency: 'RUB', prices };
        await assert.rejects(requestJson('/orders'), error => { assert.equal(error.checkoutPrices, null); return true; });
    }
    detail = { code: 'checkout_price_changed', currency: 'RUB', prices: [{ id: 'line-7', product_id: 7, price: 1500 }] };
    status = 503;
    await assert.rejects(requestJson('/orders'), error => { assert.equal(error.checkoutPrices, null); return true; });
});

test('durable order view uses customer authorization or guest capability and checks the returned order', async t => {
    const calls = [];
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        calls.push({ url, headers: new Headers(init.headers), cache: init.cache });
        return Response.json({ id: 42, status: 'pending', cart_items: '[]', total_price: 2250 });
    });
    assert.equal((await getOrderDetails('42', undefined, { kind: 'customer', token: 'session' })).id, 42);
    assert.equal((await getOrderDetails('42', undefined, { kind: 'guest', token: 'g'.repeat(43) })).id, 42);
    assert.equal(calls[0].url, '/api/orders/42');
    assert.equal(calls[0].headers.get('Authorization'), 'Bearer session');
    assert.equal(calls[0].headers.get('X-Order-Access-Token'), null);
    assert.equal(calls[1].url, '/api/order-access');
    assert.equal(calls[1].headers.get('X-Order-Access-Token'), 'g'.repeat(43));
    assert.equal(calls[1].headers.get('Authorization'), null);
    assert.equal(calls[1].cache, 'no-store');
    await assert.rejects(getOrderDetails('43', undefined, { kind: 'guest', token: 'g'.repeat(43) }), error => error.status === 404);
});
