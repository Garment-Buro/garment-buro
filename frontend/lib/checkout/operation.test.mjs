import assert from 'node:assert/strict';
import test from 'node:test';
import { CheckoutOperationController } from './operation.ts';
import { ApiError } from '../api/http.ts';

const payload = () => ({
    buyer: { name: 'Покупатель', phone: '+79001234567', email: 'buyer@example.test' },
    recipient: { name: 'Получатель', phone: '+79007654321', email: 'recipient@example.test' },
    items: [{ id: 'line-7', product_id: 7, quantity: 2, price: 1000 }],
    payment_method: 'card', delivery_method: 'cdek_pickup', delivery_city: 'Тверь',
    delivery_address: 'Советская, 1', cdek_point_code: 'TVR1', delivery_price: 250,
    delivery_quote_token: 'original-proof', claimed_total_price: 2250, currency: 'RUB',
});
const memoryStorage = () => {
    const entries = new Map();
    return { getItem: key => entries.get(key) ?? null, setItem: (key, value) => entries.set(key, value), removeItem: key => entries.delete(key) };
};
const guest = { owner: 'guest', generation: 'guest-epoch', actor: { kind: 'guest', token: '' } };

test('lost creation response and reload reuse the same operation, capability and original signed quote', async t => {
    const calls = [], orders = new Map();
    let loseResponse = true;
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        const headers = new Headers(init.headers), body = JSON.parse(init.body);
        calls.push({ url, key: headers.get('Idempotency-Key'), guest: headers.get('X-Order-Access-Token'), body });
        orders.set(headers.get('Idempotency-Key'), 42);
        if (loseResponse) { loseResponse = false; throw new TypeError('Network connection lost'); }
        return Response.json({ order_id: 42, payment_url: 'https://payments.example.test/42' });
    });
    const storage = memoryStorage(), getIdentity = () => guest;
    const first = new CheckoutOperationController({ storage, getIdentity });
    await assert.rejects(first.purchase(payload()), TypeError);
    const reloaded = new CheckoutOperationController({ storage, getIdentity });
    const result = await reloaded.purchase({ ...payload(), delivery_quote_token: 'newer-proof' });
    assert.equal(result.order_id, 42);
    assert.equal(calls.length, 2); assert.equal(orders.size, 1);
    assert.match(calls[0].guest, /^[A-Za-z0-9_-]{43}$/);
    assert.equal(calls[1].key, calls[0].key); assert.equal(calls[1].guest, calls[0].guest);
    assert.equal(calls[1].body.delivery_quote_token, 'original-proof');
    assert.equal(reloaded.pending().status, 'complete');
    assert.equal(reloaded.guestTokenForOrder(42), calls[0].guest);
});

test('double click while payment is waiting sends one purchase', async t => {
    let release, requests = 0;
    t.mock.method(globalThis, 'fetch', async () => {
        requests++;
        await new Promise(resolve => { release = resolve; });
        return Response.json({ order_id: 42 });
    });
    const controller = new CheckoutOperationController({ storage: memoryStorage(), getIdentity: () => guest });
    const first = controller.purchase(payload());
    const second = controller.purchase(payload());
    release();
    assert.equal((await first).order_id, 42); assert.equal((await second).order_id, 42);
    assert.equal(requests, 1);
});

test('changed recipient, cart or address cannot silently replace an uncertain purchase', async t => {
    let requests = 0;
    t.mock.method(globalThis, 'fetch', async () => { requests++; throw new TypeError('Offline'); });
    const controller = new CheckoutOperationController({ storage: memoryStorage(), getIdentity: () => guest });
    await assert.rejects(controller.purchase(payload()));
    for (const changed of [
        { ...payload(), recipient: { ...payload().recipient, name: 'Другой получатель' } },
        { ...payload(), items: [{ ...payload().items[0], quantity: 3 }] },
        { ...payload(), delivery_address: 'Другой адрес' },
    ]) await assert.rejects(controller.purchase(changed), /незавершённое оформление/i);
    assert.equal(requests, 1);
    await assert.rejects(controller.resume(), TypeError);
    assert.equal(requests, 2);
});

test('account switch suppresses a late result and never replays it with another actor', async t => {
    let identity = { owner: 'customer:7', generation: 'login-a', actor: { kind: 'customer', token: 'session-a' } };
    let release; const calls = [];
    t.mock.method(globalThis, 'fetch', async (_, init) => {
        calls.push(new Headers(init.headers).get('Authorization'));
        await new Promise(resolve => { release = resolve; });
        return Response.json({ order_id: 42 });
    });
    const controller = new CheckoutOperationController({ storage: memoryStorage(), getIdentity: () => identity });
    const purchase = controller.purchase(payload());
    identity = { owner: 'customer:8', generation: 'login-b', actor: { kind: 'customer', token: 'session-b' } };
    release(); await assert.rejects(purchase, { name: 'AbortError' });
    assert.equal(controller.pending(), null);
    assert.deepEqual(calls, ['Bearer session-a']);
    identity = { owner: 'customer:7', generation: 'login-c', actor: { kind: 'customer', token: 'session-c' } };
    assert.equal(controller.pending().result.order_id, 42);
});

test('known rejection retries payment on the existing order; lost retry response preserves its new payment key', async t => {
    const calls = []; let phase = 0;
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        calls.push({ url, key: new Headers(init.headers).get('Idempotency-Key'), body: init.body });
        phase++;
        if (phase === 1) return Response.json({ detail: { code: 'payment_rejected', order_id: 42 } }, { status: 502 });
        if (phase === 2) throw new TypeError('Lost retry response');
        return Response.json({ order_id: 42, payment_url: 'https://payments.example.test/retry' });
    });
    const storage = memoryStorage(), getIdentity = () => guest;
    const controller = new CheckoutOperationController({ storage, getIdentity });
    await assert.rejects(controller.purchase(payload()), error => error instanceof ApiError && error.code === 'payment_rejected');
    assert.equal(controller.pending().status, 'rejected');
    await assert.rejects(controller.retryPayment(), TypeError);
    const reloaded = new CheckoutOperationController({ storage, getIdentity });
    assert.equal((await reloaded.resume()).order_id, 42);
    assert.deepEqual(calls.map(call => call.url), ['/api/orders', '/api/orders/42/payment-attempts', '/api/orders/42/payment-attempts']);
    assert.notEqual(calls[0].key, calls[1].key);
    assert.equal(calls[1].key, calls[2].key);
    assert.equal(calls[1].body, undefined);
});

test('blocked browser storage prevents sending a purchase that cannot be recovered', async t => {
    let requests = 0;
    t.mock.method(globalThis, 'fetch', async () => { requests++; return Response.json({ order_id: 42 }); });
    const storage = { ...memoryStorage(), setItem: () => { throw new Error('Storage disabled'); } };
    const controller = new CheckoutOperationController({ storage, getIdentity: () => guest });
    await assert.rejects(controller.purchase(payload()), /сохранить операцию/i);
    assert.equal(requests, 0);
});

test('definite command rejection allows corrected purchase, malformed success remains uncertain', async t => {
    let response = Response.json({ detail: 'Invalid checkout total' }, { status: 422 });
    t.mock.method(globalThis, 'fetch', async () => response);
    const controller = new CheckoutOperationController({ storage: memoryStorage(), getIdentity: () => guest });
    await assert.rejects(controller.purchase(payload()), error => error.status === 422);
    assert.equal(controller.pending(), null);
    response = Response.json({ payment_url: 'https://payments.example.test/missing-id' });
    await assert.rejects(controller.purchase(payload()), /ответ/i);
    assert.equal(controller.pending().status, 'pending');
});

test('definite stock or catalog rejection releases the operation but generic conflicts preserve it', async t => {
    let code = 'checkout_stock_unavailable';
    const keys = [];
    t.mock.method(globalThis, 'fetch', async (_, init) => {
        keys.push(new Headers(init.headers).get('Idempotency-Key'));
        return Response.json({ detail: { code } }, { status: 409 });
    });
    const controller = new CheckoutOperationController({ storage: memoryStorage(), getIdentity: () => guest });
    for (code of ['checkout_stock_unavailable', 'checkout_catalog_unavailable', 'checkout_delivery_unavailable', 'checkout_price_changed', 'checkout_design_unavailable']) {
        await assert.rejects(controller.purchase(payload()), error => error.status === 409);
        assert.equal(controller.pending(), null);
    }
    assert.notEqual(keys[0], keys[1]);
    code = 'payment_in_progress';
    await assert.rejects(controller.purchase(payload()), error => error.status === 409);
    const key = controller.pending().idempotencyKey;
    await assert.rejects(controller.resume(), error => error.status === 409);
    assert.equal(controller.pending().idempotencyKey, key);
});

test('a managed payment rejection opens the retained order for review without attempting a forbidden new charge', async t => {
    let requests = 0;
    t.mock.method(globalThis, 'fetch', async () => {
        requests++;
        return Response.json({ detail: { code: 'payment_requires_review', order_id: 42 } }, { status: 502 });
    });
    const storage = memoryStorage();
    const controller = new CheckoutOperationController({ storage, getIdentity: () => guest });
    await assert.rejects(controller.purchase(payload()), error => error.code === 'payment_requires_review');
    assert.equal(controller.pending().status, 'review');
    assert.match(controller.guestTokenForOrder(42), /^[A-Za-z0-9_-]{43}$/);
    await assert.rejects(controller.retryPayment(), /состояние/);
    assert.equal(controller.pending().status, 'review');
    const reloaded = new CheckoutOperationController({ storage, getIdentity: () => guest });
    assert.deepEqual(await reloaded.resume(), { order_id: 42 });
    assert.equal(requests, 1);
    reloaded.finish(); // Explicitly archive a known retained order, never an unknown outcome.
    assert.equal(reloaded.pending(), null);
    assert.match(reloaded.guestTokenForOrder(42), /^[A-Za-z0-9_-]{43}$/);
});
