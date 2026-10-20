import assert from 'node:assert/strict';
import test from 'node:test';
import { getConstructorPrice, getConstructorProduct, getStorefrontOptions, getStorefrontProducts, getStorefrontProductsByIds, productConstructorHref } from './storefront.ts';
import { getFavoriteProducts, getFavoriteStatus, setProductFavorite } from './favorites.ts';

test('constructor pricing sends only compact placements on the same origin and propagates failure/cancellation', async t => {
    let captured;
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        captured = {url, init}; init.signal?.throwIfAborted();
        return Response.json({detail:'Unavailable'}, {status:503});
    });
    const input = {productId:42, decorations:[{uid:'one',scale:1.5}]};
    const controller = new AbortController();
    await assert.rejects(getConstructorPrice(input, controller.signal), error => error.status === 503);
    assert.equal(captured.url, '/api/catalog/products/42/price');
    assert.equal(captured.init.method, 'POST');
    assert.equal(captured.init.cache, 'no-store');
    assert.equal(captured.init.credentials, 'same-origin');
    assert.deepEqual(JSON.parse(captured.init.body), {decorations:[{uid:'one',scale:1.5}]});
    controller.abort();
    await assert.rejects(getConstructorPrice(input, controller.signal), {name:'AbortError'});
});

test('constructor reads one uncached public product and propagates withdrawal and cancellation', async t => {
    let captured;
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        captured = {url, init};
        init.signal?.throwIfAborted();
        return String(url).endsWith('/42') ? Response.json({schema_version:1,id:42,title:'Model',price:100,
            stock_quantity:0,sizes:[],variants:[],images:[],media_assets:[]}) : Response.json({detail:'Product not found'}, {status:404});
    });
    const controller = new AbortController();
    assert.equal((await getConstructorProduct(42, controller.signal)).id, 42);
    assert.equal(captured.url, '/api/catalog/products/42');
    assert.equal(captured.init.cache, 'no-store');
    assert.ok(captured.init.signal instanceof AbortSignal);
    assert.equal(captured.init.signal.aborted, false);
    await assert.rejects(getConstructorProduct(43), error => error.status === 404);
    controller.abort();
    await assert.rejects(getConstructorProduct(42, controller.signal), {name:'AbortError'});
});

test('storefront API serializes repeated filters, exact prices and cursor on the application origin', async t => {
    const controller = new AbortController();
    let captured;
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        captured = { url: new URL(url, 'https://site.example'), init };
        return Response.json({ items: [{ id: 42, price: '3000.50' }], next_cursor: 'next' });
    });
    const page = await getStorefrontProducts({
        query: ' Хлопок & лето ', categoryIds: [3, 4], colors: ['Белый', 'Чёрный'],
        minPrice: 0, maxPrice: 3000.5, source: 'garment_buro', sort: 'cheap',
        limit: 24, cursor: 'a+b/c==',
    }, controller.signal);
    assert.equal(captured.url.pathname, '/api/catalog/products');
    assert.equal(captured.url.searchParams.get('query'), 'Хлопок & лето');
    assert.deepEqual(captured.url.searchParams.getAll('category_ids'), ['3', '4']);
    assert.deepEqual(captured.url.searchParams.getAll('colors'), ['Белый', 'Чёрный']);
    assert.equal(captured.url.searchParams.get('min_price'), '0');
    assert.equal(captured.url.searchParams.get('max_price'), '3000.5');
    assert.equal(captured.url.searchParams.get('cursor'), 'a+b/c==');
    assert.ok(captured.init.signal instanceof AbortSignal);
    assert.equal(captured.init.signal.aborted, false);
    assert.equal(captured.init.credentials, 'same-origin');
    assert.equal(page.items[0].price, '3000.50');
});

test('default storefront queries do not silently hide inexpensive or expensive products', async t => {
    const urls = [];
    t.mock.method(globalThis, 'fetch', async url => {
        urls.push(new URL(url, 'https://site.example'));
        return Response.json({ items: [], next_cursor: null });
    });
    await getStorefrontProducts({});
    assert.equal(urls[0].searchParams.has('min_price'), false);
    assert.equal(urls[0].searchParams.has('max_price'), false);
    await getStorefrontOptions();
    assert.equal(urls[1].pathname, '/api/catalog/options');
    assert.equal(productConstructorHref(42), '/constructor?productId=42');
    assert.throws(() => productConstructorHref(0), RangeError);
    assert.throws(() => productConstructorHref('preview-hoodie'), RangeError);
});

test('favorites use account authorization, bounded membership and idempotent writes', async t => {
    const calls = [];
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        calls.push({ url: new URL(url, 'https://site.example'), init });
        return init.method ? new Response(null, {status: 204}) : Response.json({product_ids:[42]});
    });
    assert.deepEqual(await getFavoriteStatus([], 'test-session'), []);
    assert.equal(calls.length, 0);
    assert.deepEqual(await getFavoriteStatus([42, 43, 42], 'test-session'), [42]);
    assert.deepEqual(calls[0].url.searchParams.getAll('product_ids'), ['42', '43']);
    assert.equal(calls[0].init.headers.Authorization, 'Bearer test-session');
    assert.equal(calls[0].init.cache, 'no-store');
    await setProductFavorite(42, true, 'test-session');
    await setProductFavorite(42, false, 'test-session');
    assert.deepEqual(calls.slice(1).map(call => call.init.method), ['PUT', 'DELETE']);
    assert.equal(calls[1].url.pathname, '/api/profile/favorites/42');
    await getFavoriteProducts('test-session', {limit:24, cursor:51});
    assert.equal(calls[3].url.searchParams.get('cursor'), '51');
    await assert.rejects(getFavoriteStatus(Array.from({length:101}, (_, i) => i+1), 'test-session'), RangeError);
    await assert.rejects(setProductFavorite(-1, true, 'test-session'), RangeError);
    assert.equal(calls.length, 4);
});

test('catalog cancellation and favorite write failures reach the caller for honest UI state', async t => {
    const controller = new AbortController();
    controller.abort();
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        init.signal?.throwIfAborted();
        return Response.json({detail:'Write rejected'}, {status:409});
    });
    await assert.rejects(getStorefrontProducts({}, controller.signal), {name:'AbortError'});
    await assert.rejects(setProductFavorite(42, true, 'test-session'), error => error.status === 409);
});

test('favorite card lookup preserves saved order and never requests the whole catalog for an empty list', async t => {
    const calls = [];
    t.mock.method(globalThis, 'fetch', async url => {
        calls.push(new URL(url, 'https://site.example'));
        return Response.json({items:[{id:43}, {id:42}], next_cursor:null});
    });
    assert.deepEqual(await getStorefrontProductsByIds([]), []);
    assert.equal(calls.length, 0);
    assert.deepEqual(await getStorefrontProductsByIds([42, 99, 43, 42]), [{id:42}, {id:43}]);
    assert.deepEqual(calls[0].searchParams.getAll('ids'), ['42', '99', '43']);
    assert.equal(calls[0].searchParams.get('limit'), '3');
});
