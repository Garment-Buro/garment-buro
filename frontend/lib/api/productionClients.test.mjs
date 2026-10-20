import assert from 'node:assert/strict';
import test from 'node:test';
import { requestClientOrders, requestClientTickets } from './productionClients.ts';
import { readClientOrders, readClientTickets } from '../production/clientHistory.ts';
import { PageCursorExpiredError, PagedResource } from '../catalog/pagedResource.ts';

const order = (id = 1) => ({ id, created_at: '2025-01-01T00:00:00Z', total: '80.00', status: 'new',
    payment_status: 'pending', workflow_state: null, delivery_city: null, delivery_method: null, payment_method: null });
const ticket = (id = 1) => ({ id, subject: 'Обращение', status: 'new', priority: 'normal', order_id: null,
    created_at: '2025-01-01T00:00:00Z', updated_at: '2025-01-01T00:00:00Z' });
const page = (item, next_cursor = null) => ({ items: [item], next_cursor });

test('client histories stay on the same origin, bounded, private and keyed by exact client', async t => {
    const calls = [];
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        calls.push({ url, init });
        return Response.json(page(url.includes('/orders?') ? order() : ticket()));
    });
    for (const read of [requestClientOrders, requestClientTickets]) await read({ key: 'email:_%+ & Ж@example.test', cursor: 'opaque+=' });
    for (const { url, init } of calls) {
        assert.ok(url.startsWith('/api/production/admin/clients/'));
        const query = new URL(url, 'https://test.invalid').searchParams;
        assert.equal(query.get('key'), 'email:_%+ & Ж@example.test');
        assert.equal(query.get('cursor'), 'opaque+=');assert.equal(query.get('limit'), '24');
        assert.equal(init.cache, 'no-store');assert.equal(init.credentials, 'same-origin');
    }
});

test('client history parsers reject malformed pages, duplicates and invalid summaries', () => {
    for (const [read, item, changes] of [[readClientOrders, order(), [{ total: '-1' }, { total: 'NaN' }, { payment_status: null }, { delivery_city: 1 }]],
        [readClientTickets, ticket(), [{ status: 'unknown' }, { priority: 'unknown' }, { order_id: -1 }, { updated_at: 'yesterday' }]]]) {
        assert.deepEqual(read(page(item)), page(item));
        for (const malformed of [null, [], { items: [], next_cursor: '' }, { items: [item, item], next_cursor: null },
            { items: Array.from({ length: 101 }, (_, i) => ({ ...item, id: i + 1 })), next_cursor: null },
            ...[{ id: 0 }, { created_at: 'invalid' }, ...changes].map(change => page({ ...item, ...change }))]) assert.throws(() => read(malformed));
    }
});

test('append failure preserves existing history and retries the same cursor without duplicate rows', async t => {
    let failure = true;
    const cursors = [];
    t.mock.method(globalThis, 'fetch', async url => {
        const cursor = new URL(url, 'https://test.invalid').searchParams.get('cursor');cursors.push(cursor);
        if (cursor && failure) return Response.json({ detail: 'Временная ошибка' }, { status: 503 });
        return Response.json(cursor ? { items: [order(1), order(2)], next_cursor: null } : page(order(1), 'next'));
    });
    const resource = new PagedResource();t.after(() => resource.dispose());
    await resource.start('user:3', (cursor, signal) => requestClientOrders({ key: 'user:3', cursor }, { signal }));
    await resource.loadMore();assert.equal(resource.getSnapshot().items.length, 1);
    assert.equal(resource.getSnapshot().nextCursor, 'next');assert.ok(resource.getSnapshot().error);
    failure = false;await resource.loadMore();
    assert.deepEqual(resource.getSnapshot().items.map(item => item.id), [1, 2]);
    assert.deepEqual(cursors, [null, 'next', 'next']);
});

test('invalid history cursor retains rows and requires explicit refresh', async t => {
    let invalid = false;
    t.mock.method(globalThis, 'fetch', async () => invalid
        ? Response.json({ detail: { code: 'invalid_cursor' } }, { status: 422 }) : Response.json(page(ticket(), 'next')));
    const resource = new PagedResource();t.after(() => resource.dispose());
    await resource.start('user:3', (cursor, signal) => requestClientTickets({ key: 'user:3', cursor }, { signal }));
    invalid = true;await resource.loadMore();
    assert.ok(resource.getSnapshot().error instanceof PageCursorExpiredError);
    assert.equal(resource.getSnapshot().items.length, 1);
    invalid = false;await resource.reload();assert.equal(resource.getSnapshot().error, null);
});

test('history reads cancel and time out without automatic retry', async t => {
    t.mock.timers.enable({ apis: ['setTimeout'] });let calls = 0;
    t.mock.method(globalThis, 'fetch', (_url, init) => { calls++;return new Promise((_, reject) =>
        init.signal.addEventListener('abort', () => reject(init.signal.reason), { once: true })); });
    const timed = assert.rejects(requestClientOrders({ key: 'user:3' }), { name: 'TimeoutError' });
    t.mock.timers.tick(10000);await timed;
    const controller = new AbortController();
    const cancelled = assert.rejects(requestClientTickets({ key: 'user:3' }, { signal: controller.signal }), { name: 'AbortError' });
    controller.abort();await cancelled;assert.equal(calls, 2);
});
