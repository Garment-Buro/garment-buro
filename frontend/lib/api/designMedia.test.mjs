import assert from 'node:assert/strict';
import test from 'node:test';
import { DESIGN_IMAGE_MAX_BYTES, importDesignImages, readDesignImage, uploadDesignImage } from './designMedia.ts';

const path = '/api/design-media/' + 'a'.repeat(43) + '/content';
const image = () => ({ url: path, content_type: 'image/webp', size_bytes: 1024, expires_at: '2030-01-01T00:00:00Z' });

test('upload sends raw raster bytes to same-origin API; private import is one authenticated ID batch', async t => {
    const calls = [];
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        calls.push({ url, init });
        return Response.json(url.endsWith('/import') ? { items: [{ ...image(), media_id: 12 }] } : image());
    });
    const blob = new Blob(['raster'], { type: 'image/png' }), signal = new AbortController().signal;
    assert.equal((await uploadDesignImage(blob, signal)).url, path);
    assert.equal((await importDesignImages([12, 12], 'session', signal))[0].media_id, 12);
    assert.deepEqual(calls.map(call => call.url), ['/api/design-media', '/api/design-media/import']);
    assert.equal(calls[0].init.body, blob);
    assert.equal(calls[0].init.headers['Content-Type'], 'image/png');
    assert.equal(calls[0].init.headers.Authorization, undefined);
    assert.equal(calls[1].init.headers.Authorization, 'Bearer session');
    assert.deepEqual(JSON.parse(calls[1].init.body), { media_ids: [12] });
    for (const { init } of calls) { assert.equal(init.signal, signal); assert.equal(init.cache, 'no-store'); }
});

test('invalid files and ID batches never reach the API', async t => {
    let calls = 0;
    t.mock.method(globalThis, 'fetch', async () => { calls++; throw new Error('Unexpected network'); });
    for (const blob of [new Blob([], { type: 'image/png' }), new Blob(['svg'], { type: 'image/svg+xml' }), new Blob([new Uint8Array(DESIGN_IMAGE_MAX_BYTES + 1)], { type: 'image/png' })]) await assert.rejects(uploadDesignImage(blob), RangeError);
    for (const ids of [[], [0], [2 ** 32], [true], Array.from({ length: 103 }, (_, i) => i + 1)]) await assert.rejects(importDesignImages(ids, 'session'), RangeError);
    assert.equal(calls, 0);
});

test('foreign URLs, incomplete imports and malformed upload confirmations cannot become saved references', async t => {
    let response = { ...image(), url: 'https://foreign.test' + path };
    t.mock.method(globalThis, 'fetch', async () => Response.json(response));
    const blob = new Blob(['png'], { type: 'image/png' });
    for (const invalid of [{ ...image(), url: path + '?x=1' }, { ...image(), size_bytes: 0 }, { ...image(), expires_at: 'bad' }, response]) {
        response = invalid; await assert.rejects(uploadDesignImage(blob));
    }
    for (const items of [[], [{ ...image(), media_id: 13 }], [{ ...image(), media_id: 12 }, { ...image(), media_id: 12 }]]) {
        response = { items }; await assert.rejects(importDesignImages([12], 'session'));
    }
});

test('copying an existing cart image reads only its exact capability route, with no-store and bounded bytes', async t => {
    const calls = [];
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        calls.push({ url, init }); return new Response('webp', { headers: { 'Content-Type': 'image/webp' } });
    });
    assert.equal(await (await readDesignImage(path)).text(), 'webp');
    assert.equal(calls[0].url, path); assert.equal(calls[0].init.cache, 'no-store');
    assert.equal(calls[0].init.referrerPolicy, 'no-referrer');
    for (const url of ['https://foreign.test' + path, path + '?x=1', '/uploads/arbitrary.png']) await assert.rejects(readDesignImage(url));
    assert.equal(calls.length, 1);
    t.mock.method(globalThis, 'fetch', async () => new Response(new Uint8Array(DESIGN_IMAGE_MAX_BYTES + 1), { headers: { 'Content-Type': 'image/png' } }));
    await assert.rejects(readDesignImage(path), /слишком большое/);
});
