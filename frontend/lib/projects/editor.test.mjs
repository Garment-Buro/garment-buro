import assert from 'node:assert/strict';
import test from 'node:test';
import { ProjectEditor } from './editor.ts';
import { createProjectImageResolver } from './images.ts';

const image = 'data:image/png;base64,aW1hZ2U=';
const draft = () => ({
    activeView: 'front', canvasPixelSize: { width: 800, height: 800 },
    modelBounds: { x: 0, y: 0, width: 300, height: 400 },
    customization: {
        kind: 'constructor', selectedSize: 'M', modelImages: { front: '/front.webp', back: '/front.webp' },
        canvas: { widthCm: 80, heightCm: 80 }, garment: { widthCm: 60, heightCm: 75 },
        decorations: [{ uid: 'item_1', variantId: 'custom_1', view: 'front', name: 'Мой принт',
            price: 80, image, x: 100, y: 150, scale: 1, rotation: 0, widthCm: 20, heightCm: 20 }],
        totalPrice: 1080,
    },
});
const input = () => ({ productId: 17, title: 'Мой проект', kind: 'draft', draft: draft(), assets: [{ id: 12, url: '/front.webp' }] });
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
function server() {
    let document, uploads = 0, creates = [], updates = [], loseResponse = false, loseUpdate = false;
    return {
        transport: {
            upload: async () => ({ id: 99 + ++uploads, content_type: 'image/webp', size_bytes: 5 }),
            create: async payload => {
                creates.push(structuredClone(payload));
                if (!document) document = { ...structuredClone(payload), id: 42, version: 1 };
                if (loseResponse) { loseResponse = false; throw new TypeError('Response lost'); }
                return structuredClone(document);
            },
            update: async (id, payload) => {
                updates.push({ id, ...structuredClone(payload) });
                if (payload.expected_version !== document.version) throw Object.assign(new Error('Conflict'), { status: 409 });
                document = { ...document, ...structuredClone(payload), version: document.version + 1 };
                if (loseUpdate) { loseUpdate = false; throw new TypeError('Response lost'); }
                return structuredClone(document);
            },
            get: async () => structuredClone(document),
            images: async () => ({ version: document.version, items: [{ id: 12, url: '/front.webp', expires_in: null }, { id: 100, url: '/signed.webp', expires_in: 600 }] }),
        },
        get creates() { return creates; }, get updates() { return updates; }, get uploads() { return uploads; },
        loseNextResponse() { loseResponse = true; },
        loseNextUpdateResponse() { loseUpdate = true; },
        advanceVersion() { document.version++; },
    };
}

test('project image resolution reuses server identities and uploads only local user image bytes', async () => {
    let uploads = 0;
    const references = new Map([['/front.webp', { mediaId: 12 }]]);
    const resolve = createProjectImageResolver({ origin: 'https://site.test', references,
        upload: async blob => { assert.equal(await blob.text(), 'image'); uploads++; return { id: 100 }; } });
    assert.deepEqual(await resolve('/front.webp'), { mediaId: 12 });
    assert.deepEqual(await resolve(image), { mediaId: 100 });
    assert.deepEqual(await resolve(image), { mediaId: 100 });
    assert.equal(uploads, 1);
    for (const source of ['https://evil.test/image.png', '/mock-design_1.png', 'data:image/svg+xml,<svg/>', 'blob:https://evil.test/id']) {
        await assert.rejects(resolve(source), /image|изображен/i);
    }
    const controller = new AbortController(); controller.abort();
    await assert.rejects(resolve('/front.webp', controller.signal), { name: 'AbortError' });
});

test('purchase receives trusted public URLs and private media identities; account disposal clears both', async () => {
    const api = server(), editor = new ProjectEditor({ origin: 'https://site.test' });
    editor.setAccount('user:one', api.transport);
    await editor.save(input());
    const saved = editor.getImageSources();
    assert.deepEqual([...saved.publicImages], ['/front.webp']);
    assert.equal(saved.privateImages.get(image), 100);
    saved.privateImages.clear();
    assert.equal(editor.getImageSources().privateImages.get(image), 100);
    await editor.load(42);
    assert.equal(editor.getImageSources().privateImages.get('/signed.webp'), 100);
    assert.deepEqual([...editor.getImageSources().publicImages], ['/front.webp']);
    editor.setAccount('user:two', api.transport);
    assert.equal(editor.getImageSources().privateImages.size, 0);
    assert.equal(editor.getImageSources().publicImages.size, 0);
});

test('saving a cart design to an owned project copies capability bytes once and reuses its new private ID', async t => {
    const capability = '/api/design-media/' + 'a'.repeat(43) + '/content';
    const downloads = [];
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        downloads.push({ url, init });
        return new Response('pixels', { headers: { 'Content-Type': 'image/webp' } });
    });
    let uploads = 0;
    const resolver = createProjectImageResolver({ origin: 'https://site.test', references: new Map(), upload: async blob => {
        uploads++; assert.equal(await blob.text(), 'pixels'); return { id: 77 };
    } });
    assert.deepEqual(await resolver(capability), { mediaId: 77 });
    assert.deepEqual(await resolver(capability), { mediaId: 77 });
    assert.equal(downloads.length, 1); assert.equal(downloads[0].url, capability); assert.equal(uploads, 1);
    await assert.rejects(resolver('https://foreign.test' + capability));
    assert.equal(downloads.length, 1);
});

test('unknown create outcome retries the original document/key and never silently claims later edits were saved', async () => {
    const api = server(), editor = new ProjectEditor({ origin: 'https://site.test' });
    editor.setAccount('user:one', api.transport);
    const original = input(); api.loseNextResponse();
    assert.equal(await editor.save(original), null);
    assert.ok(editor.getSnapshot().error instanceof TypeError);
    const changed = structuredClone(original); changed.draft.customization.comment = 'Более новая правка';
    const recovered = await editor.save(changed);
    assert.equal(recovered.matchesDraft, false);
    assert.equal(recovered.document.id, 42);
    assert.deepEqual(api.creates[0], api.creates[1]);
    assert.equal(api.uploads, 1); assert.equal(api.updates.length, 0);
    const saved = await editor.save(changed);
    assert.equal(saved.matchesDraft, true);
    assert.equal(saved.document.version, 2);
    assert.equal(api.updates[0].expected_version, 1);
    assert.equal(api.updates[0].snapshot.customization.comment, 'Более новая правка');
});

test('conflicting server version keeps the editing version until an explicit reload', async () => {
    const api = server(), editor = new ProjectEditor({ origin: 'https://site.test' });
    editor.setAccount('user:one', api.transport);
    await editor.save(input()); api.advanceVersion();
    assert.equal(await editor.save(input()), null);
    assert.equal(editor.getSnapshot().error.status, 409);
    assert.equal(editor.getSnapshot().document.version, 1);
    assert.equal(await editor.load(42), true);
    assert.equal(editor.getSnapshot().document.version, 2);
    assert.equal(editor.getSnapshot().restored.customization.decorations[0].image, '/signed.webp');
});

test('account change aborts saving and prevents late documents or uploaded IDs reaching the next account', async () => {
    const api = server(), editor = new ProjectEditor({ origin: 'https://site.test' }), gate = deferred();
    let signal;
    editor.setAccount('user:one', { ...api.transport, create: async (_payload, requestSignal) => { signal = requestSignal; return gate.promise; } });
    const saving = editor.save(input());
    while (!signal) await new Promise(r => setTimeout(r, 0));
    editor.setAccount('user:two', api.transport);
    assert.equal(signal.aborted, true);
    gate.resolve({ id: 42, version: 1 });
    assert.equal(await saving, null);
    assert.equal(editor.getSnapshot().document, null);
    await editor.save(input());
    assert.equal(api.uploads, 2);
});

test('loading rejects mixed versions and cannot turn a failed existing-project load into a new project', async () => {
    const api = server(), editor = new ProjectEditor({ origin: 'https://site.test' });
    editor.setAccount('user:one', api.transport); await editor.save(input());
    editor.setAccount('user:one:new-session', { ...api.transport, images: async () => ({ version: 999, items: [] }) });
    assert.equal(await editor.load(42), false);
    assert.equal(editor.getSnapshot().restored, null);
    assert.equal(await editor.save(input()), null);
    assert.equal(api.creates.length, 1);
});

test('a rejected document can be corrected instead of retrying a permanently invalid POST', async () => {
    const api = server(), editor = new ProjectEditor({ origin: 'https://site.test' });
    let rejected = true;
    editor.setAccount('user:one', { ...api.transport, create: async (payload, signal) => {
        if (rejected) { rejected = false; throw Object.assign(new Error('Invalid document'), { status: 422 }); }
        return api.transport.create(payload, signal);
    } });
    const original = input(); assert.equal(await editor.save(original), null);
    const corrected = input(); corrected.title = 'Исправленный проект';
    const saved = await editor.save(corrected);
    assert.equal(saved.matchesDraft, true);
    assert.equal(saved.document.title, 'Исправленный проект');
});

test('conflict recovery reloads a confirmed project even before the route receives its ID', async () => {
    const api = server(), editor = new ProjectEditor({ origin: 'https://site.test' });
    editor.setAccount('user:one', api.transport);
    const original = input(); api.loseNextResponse();
    await editor.save(original);
    const changed = input(); changed.draft.customization.comment = 'Новые правки';
    assert.equal((await editor.save(changed)).matchesDraft, false);
    api.loseNextUpdateResponse();
    assert.equal(await editor.save(changed), null);
    assert.equal(await editor.save(changed), null);
    assert.equal(editor.getSnapshot().error.status, 409);
    assert.equal(await editor.reload(), true);
    assert.equal(editor.getSnapshot().document.version, 2);
    assert.equal(editor.getSnapshot().restored.customization.comment, 'Новые правки');
});

test('a failed reload keeps the editing document and a later retry can recover it', async () => {
    const api = server(), editor = new ProjectEditor({ origin: 'https://site.test' });
    let offline = false;
    editor.setAccount('user:one', { ...api.transport, get: async (...args) => {
        if (offline) throw new TypeError('Offline');
        return api.transport.get(...args);
    } });
    await editor.save(input()); await editor.load(42);
    const before = editor.getSnapshot();
    offline = true;
    assert.equal(await editor.load(42), false);
    assert.equal(editor.getSnapshot().document, before.document);
    assert.equal(editor.getSnapshot().restored, before.restored);
    offline = false;
    assert.equal(await editor.load(42), true);
});

test('an obsolete metadata response must not start a dependent private image request',async()=>{
    const api=server(),editor=new ProjectEditor({origin:'https://site.test'}),pending=deferred();let imageReads=0;
    editor.setAccount('one',{...api.transport,get:async()=>pending.promise,images:async()=>{imageReads++;return {version:1,items:[]};}});
    const loading=editor.load(42);editor.setAccount('two',api.transport);
    pending.resolve({id:42,version:1,snapshot:{}});assert.equal(await loading,false);
    assert.equal(imageReads,0);assert.equal(editor.getSnapshot().document,null);
    editor.dispose();
});
