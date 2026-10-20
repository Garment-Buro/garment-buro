import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../../public/sw.js', import.meta.url), 'utf8');
const origin = 'https://garment-buro.test';

// Execute the shipped worker; only browser network/CacheStorage are replaced.
function worker() {
    const handlers = new Map();
    const stores = new Map();
    const key = request => new URL(typeof request === 'string' ? request : request.url, origin).href;
    const caches = {
        async open(name) {
            if (!stores.has(name)) stores.set(name, new Map());
            const entries = stores.get(name);
            return {
                async put(request, response) { entries.set(key(request), response.clone()); },
                async match(request) { return entries.get(key(request))?.clone(); },
                async addAll(urls) {
                    for (const url of urls) entries.set(key(url), new Response(url === '/offline.html' ? 'Offline shell' : 'Asset'));
                },
            };
        },
        async keys() { return [...stores.keys()]; },
        async delete(name) { return stores.delete(name); },
        async match(request) {
            for (const entries of stores.values()) {
                if (entries.has(key(request))) return entries.get(key(request)).clone();
            }
        },
    };
    let network = async () => new Response('Published name and bio', { headers: { 'Cache-Control': 'no-store' } });
    vm.runInNewContext(source, {
        URL, Response, caches,
        fetch: request => network(request),
        self: { location: { origin }, clients: { claim: async () => {} }, skipWaiting() {}, addEventListener: (name, handler) => handlers.set(name, handler) },
    });
    return {
        caches,
        setNetwork(value) { network = value; },
        async lifecycle(name) {
            let pending;
            handlers.get(name)({ waitUntil(value) { pending = value; } });
            await pending;
        },
        async request(path, mode = 'navigate') {
            let response;
            handlers.get('fetch')({ request: { url: origin + path, mode, method: 'GET' }, respondWith(value) { response = value; } });
            return response;
        },
    };
}

test('navigation never persists profile or home HTML and offline uses only the generic shell', async () => {
    const sw = worker();
    await sw.lifecycle('install');
    for (const path of ['/people/member', '/']) {
        sw.setNetwork(async () => new Response('Published name and bio', { headers: { 'Cache-Control': 'no-store' } }));
        assert.equal(await (await sw.request(path)).text(), 'Published name and bio');
        assert.equal(await sw.caches.match(path), undefined);
        sw.setNetwork(async () => new Response('Unavailable', { status: 404 }));
        assert.equal((await sw.request(path)).status, 404);
        sw.setNetwork(async () => { throw new TypeError('Offline'); });
        assert.equal(await (await sw.request(path)).text(), 'Offline shell');
    }
});

test('activation removes HTML saved by the previous worker before serving offline navigation', async () => {
    const sw = worker();
    const old = await sw.caches.open('garment-buro-shell-v2');
    await old.put('/people/member', new Response('Revoked profile'));
    await old.put('/', new Response('Old people cards'));
    await sw.lifecycle('install');
    await sw.lifecycle('activate');
    assert.equal(await sw.caches.match('/people/member'), undefined);
    assert.equal(await sw.caches.match('/'), undefined);
    sw.setNetwork(async () => { throw new TypeError('Offline'); });
    assert.equal(await (await sw.request('/people/member')).text(), 'Offline shell');
});

test('assets remain available offline while private APIs and terminals bypass the worker', async () => {
    const sw = worker();
    await sw.lifecycle('install');
    sw.setNetwork(async () => new Response('Static bundle'));
    assert.equal(await (await sw.request('/_next/static/chunk.js', 'cors')).text(), 'Static bundle');
    // The worker starts its asset write without blocking the network response.
    await new Promise(resolve => setImmediate(resolve));
    sw.setNetwork(async () => { throw new TypeError('Offline'); });
    assert.equal(await (await sw.request('/_next/static/chunk.js', 'cors')).text(), 'Static bundle');
    for (const path of ['/api/people/member/avatar/1', '/storage/private', '/uploads/private', '/production']) {
        assert.equal(await sw.request(path), undefined);
    }
});
