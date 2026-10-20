import assert from 'node:assert/strict';
import test from 'node:test';
import { DeliveryQuoteController } from './quote.ts';

const request = { city: 'Тверь', delivery_method: 'cdek_pickup', cdek_point_code: 'TVR1', cart_items: [{ product_id: 7, quantity: 2 }] };
const response = (token = 'proof') => ({ delivery_price: 250, quote_token: token, delivery_city: 'Тверь', delivery_address: 'Советская, 1', cdek_point_code: 'TVR1', tariff_code: 136, currency: 'RUB' });

test('closed form makes no quote request and cancelling hides its earlier tariff', async t => {
    let requests = 0, signal, release;
    t.mock.method(globalThis, 'fetch', async (_, init) => {
        requests++; signal = init.signal;
        await new Promise(resolve => { release = resolve; });
        return Response.json(response());
    });
    const controller = new DeliveryQuoteController();
    await controller.update(request, false);
    assert.equal(requests, 0);
    const pending = controller.update(request, true);
    await controller.update(request, false);
    assert.equal(signal.aborted, true);
    release(); await pending;
    assert.equal(controller.getSnapshot().quote, null);
    assert.equal(controller.getSnapshot().status, 'idle');
});

test('a changed point or quantity invalidates the old quote immediately and ignores a late response', async t => {
    const waiting = [];
    t.mock.method(globalThis, 'fetch', async (_, init) => {
        const body = JSON.parse(init.body);
        return await new Promise(resolve => waiting.push({ body, signal: init.signal, resolve }));
    });
    const controller = new DeliveryQuoteController();
    const first = controller.update(request, true);
    const second = controller.update({ ...request, cdek_point_code: 'TVR2', cart_items: [{ product_id: 7, quantity: 3 }] }, true);
    assert.equal(controller.getSnapshot().quote, null);
    assert.equal(waiting[0].signal.aborted, true);
    waiting[1].resolve(Response.json({ ...response('new-proof'), cdek_point_code: 'TVR2', delivery_address: 'Советская, 2' })); await second;
    waiting[0].resolve(Response.json(response('old-proof'))); await first;
    assert.equal(controller.getSnapshot().quote.quote_token, 'new-proof');
    assert.equal(waiting[1].body.cdek_point_code, 'TVR2');
    assert.equal(waiting[1].body.cart_items[0].quantity, 3);
});

test('failed and expired quotes cannot remain usable or become free delivery', async t => {
    let now = 0, fail = false;
    t.mock.method(globalThis, 'fetch', async () => fail ? Response.json({ detail: 'Unavailable' }, { status: 503 }) : Response.json(response()));
    const controller = new DeliveryQuoteController(() => now);
    await controller.update(request, true);
    assert.equal(controller.getSnapshot().status, 'ready');
    now = 15 * 60 * 1000;
    controller.expire();
    assert.equal(controller.getSnapshot().quote, null);
    fail = true;
    await controller.update(request, true);
    assert.equal(controller.getSnapshot().status, 'error');
    assert.equal(controller.getSnapshot().quote, null);
});
