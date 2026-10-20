import assert from 'node:assert/strict';
import test from 'node:test';
import { ConstructorCartPreparation } from './cartPreparation.ts';

const path = character => '/api/design-media/' + character.repeat(43) + '/content';
const image = character => ({ url: path(character), content_type: 'image/webp', size_bytes: 1234, expires_at: '2030-01-01T00:00:00Z' });
const data = 'data:image/png;base64,' + Buffer.alloc(100_000, 7).toString('base64');
const second = 'data:image/png;base64,aW1hZ2U=';
const payload = () => ({
    product_id: 7, title: 'Модель', quantity: 3, image: '/front.webp', size: 'M', color: 'black', price: 180,
    customization: { kind: 'constructor', modelImages: { front: '/front.webp', back: '/front.webp' },
        selectedSize: 'M', totalPrice: 180, comment: 'Сохранить расположение',
        canvas: { widthCm: 100, heightCm: 90 }, garment: { widthCm: 60, heightCm: 65 },
        fit: { lengthCm: 188 }, geometry: { canvasPixelSize: { width: 1000, height: 900 }, modelBounds: { x: 200, y: 180, width: 600, height: 650 } },
        decorations: [{ uid: 'one', image: data, scale: 1, x: 330, y: 470, widthCm: 12, heightCm: 5, text: { content: 'Текст' } }],
    },
});
const sources = () => ({ publicImages: new Set(['/front.webp']), privateImages: new Map() });
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const defaults = () => ({ origin: 'https://site.test', getScope: () => 'guest', now: () => Date.parse('2026-10-18'), upload: async () => image('a'), import: async () => { throw new Error('Unexpected import'); } });

test('large inline image becomes one durable URL; geometry, human height, text and input remain intact', async () => {
    let uploads = 0, committed;
    const original = payload(), snapshot = structuredClone(original);
    original.customization.decorations.push({ ...original.customization.decorations[0], uid: 'two' });
    snapshot.customization.decorations.push({ ...snapshot.customization.decorations[0], uid: 'two' });
    const preparation = new ConstructorCartPreparation({ ...defaults(), upload: async blob => { uploads++; assert.equal(blob.size, 100_000); return image('a'); } });
    assert.equal(await preparation.submit(original, sources(), result => { committed = result; }), true);
    assert.equal(uploads, 1);
    assert.deepEqual(original, snapshot);
    const expected = structuredClone(original); expected.customization.decorations.forEach(item => { item.image = path('a'); });
    assert.deepEqual(committed, expected);
    assert.ok(new TextEncoder().encode(JSON.stringify(committed.customization)).length < 64 * 1024);
    assert.equal(preparation.getSnapshot(), false);
});

test('private project images are imported by deduplicated IDs without downloading expiring URLs', async t => {
    const calls = [], committed = [], source = 'https://private.test/image?X-Amz-Signature=expired';
    t.mock.method(globalThis, 'fetch', async () => { throw new Error('No URL download allowed'); });
    const input = payload(); input.image = source; input.customization.modelImages = { front: source, back: source };
    input.customization.decorations[0].image = source;
    const preparation = new ConstructorCartPreparation({ ...defaults(), import: async ids => { calls.push(ids); return [{ ...image('b'), media_id: 12 }]; } });
    await preparation.submit(input, { publicImages: new Set(), privateImages: new Map([[source, 12]]) }, result => committed.push(result));
    assert.deepEqual(calls, [[12]]);
    assert.equal(committed[0].image, path('b'));
    assert.equal(committed[0].customization.modelImages.back, path('b'));
    assert.equal(committed[0].customization.decorations[0].image, path('b'));
});

test('partial upload failure leaves cart untouched; explicit retry reuses confirmed files', async () => {
    let uploads = 0, fail = true, commits = 0;
    const input = payload(); input.customization.decorations.push({ uid: 'two', image: second });
    const preparation = new ConstructorCartPreparation({ ...defaults(), upload: async () => {
        uploads++; if (uploads === 2 && fail) throw new TypeError('Lost response'); return image(uploads === 1 ? 'a' : 'b');
    } });
    await assert.rejects(preparation.submit(input, sources(), () => { commits++; }), TypeError);
    assert.equal(commits, 0); assert.equal(preparation.getSnapshot(), false);
    fail = false; await preparation.submit(input, sources(), () => { commits++; });
    assert.equal(uploads, 3); assert.equal(commits, 1);
});

test('double click commits once and cancellation suppresses even a transport which returns late', async () => {
    let commits = 0; const gate = deferred();
    const preparation = new ConstructorCartPreparation({ ...defaults(), upload: async () => gate.promise });
    const first = preparation.submit(payload(), sources(), () => { commits++; });
    assert.equal(await preparation.submit(payload(), sources(), () => { commits++; }), false);
    preparation.cancel(); gate.resolve(image('a'));
    await assert.rejects(first, { name: 'AbortError' });
    assert.equal(commits, 0); assert.equal(preparation.getSnapshot(), false);
});

test('account change cannot publish or reuse an earlier account file', async () => {
    let scope = 'user:one', uploads = 0, commits = 0; const gate = deferred();
    const preparation = new ConstructorCartPreparation({ ...defaults(), getScope: () => scope, upload: async () => { uploads++; return uploads === 1 ? gate.promise : image('b'); } });
    const first = preparation.submit(payload(), sources(), () => { commits++; });
    while (!uploads) await new Promise(resolve => setTimeout(resolve, 0));
    scope = 'user:two'; preparation.reset(); gate.resolve(image('a'));
    await assert.rejects(first, { name: 'AbortError' });
    await preparation.submit(payload(), sources(), result => { commits++; assert.equal(result.customization.decorations[0].image, path('b')); });
    assert.equal(uploads, 2); assert.equal(commits, 1);
});

test('unknown remote images fail before upload; existing cart capabilities are reused without I/O', async () => {
    let uploads = 0, commits = 0;
    const preparation = new ConstructorCartPreparation({ ...defaults(), upload: async () => { uploads++; return image('a'); } });
    const invalid = payload(); invalid.customization.decorations.push({ uid: 'bad', image: 'https://foreign.test/image.png' });
    await assert.rejects(preparation.submit(invalid, sources(), () => { commits++; }), /Загрузите свой файл/);
    assert.equal(uploads, 0); assert.equal(commits, 0);
    const saved = payload(); saved.customization.decorations[0].image = path('b');
    await preparation.submit(saved, sources(), () => { commits++; });
    assert.equal(uploads, 0); assert.equal(commits, 1);
});

test('expired retry cache is replaced and changed cart commit failures preserve editor input', async () => {
    let uploads = 0, now = Date.parse('2026-10-18');
    const preparation = new ConstructorCartPreparation({ ...defaults(), now: () => now, upload: async () => { uploads++; return image('a'); } });
    const input = payload(), original = structuredClone(input);
    await assert.rejects(preparation.submit(input, sources(), () => { throw new Error('Cart changed'); }), /Cart changed/);
    now = Date.parse('2031-01-01');
    await preparation.submit(input, sources(), () => {});
    assert.equal(uploads, 2); assert.deepEqual(input, original);
});
