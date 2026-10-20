import assert from 'node:assert/strict';
import test from 'node:test';
import * as migration from './legacyMigration.ts';
import { LEGACY_CONSTRUCTOR_DRAFTS_STORAGE_KEY as draftsKey, LEGACY_COLLECTION_STORAGE_KEY as collectionKey } from './legacyRecords.ts';

const raster = 'data:image/png;base64,aW1hZ2U=';
const legacy = () => ({
    id: 'draft-100-17', kind: 'draft', number: '001', name: 'Старый проект',
    imageSrc: '/front.webp', productId: 17, savedAt: 100,
    draftState: {
        activeView: 'back', canvasPixelSize: { width: 1000, height: 900 },
        modelBounds: { x: 150, y: 85, width: 600, height: 700 },
        customization: {
            kind: 'constructor', selectedSize: 'M', modelImages: { front: '/front.webp', back: '/front.webp' },
            canvas: { widthCm: 100, heightCm: 75 }, garment: { widthCm: 60, heightCm: 70 },
            decorations: [{ uid: 'print', variantId: 'custom', view: 'back', name: 'Принт',
                price: 80, image: raster, x: 210, y: 111, scale: 1.1, rotation: 35, widthCm: 20.4, heightCm: 15.8 }],
            totalPrice: 1080, comment: 'Сохранить расположение',
        },
    },
});
function storageFor(values = [legacy()]) {
    const data = new Map([[draftsKey, JSON.stringify(values)]]);
    return { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value) };
}
const statusError = status => Object.assign(new Error('API failure'), { status });
function setup(storage = storageFor()) {
    let uploads = 0, creates = 0, products = 0;
    const documents = new Map();
    const transport = {
        receipt: async key => documents.get(key) ?? null,
        product: async id => { products++; assert.equal(id, 17); return { id: 17, media_assets: [{ id: 12, url: '/front.webp' }] }; },
        upload: async () => ({ id: 99 + ++uploads }),
        create: async payload => {
            creates++;
            assert.equal(payload.product_id, 17);
            if (documents.has(payload.client_key)) throw statusError(409);
            const document = { id: 42, product_id: 17, kind: payload.kind, title: payload.title,
                version: 1, created_at: '2026-10-14T00:00:00Z', updated_at: '2026-10-14T00:00:00Z', snapshot: payload.snapshot };
            documents.set(payload.client_key, document);
            return document;
        },
    };
    return { storage, transport, documents, get uploads() { return uploads; }, get creates() { return creates; }, get products() { return products; } };
}
function entry(storage) {
    assert.equal(typeof migration.scanLegacyProjects, 'function', 'Legacy projects need a lossless migration reader');
    return migration.scanLegacyProjects(storage).entries[0];
}
const options = setup => ({ storage: setup.storage, transport: setup.transport, origin: 'https://site.test', signal: new AbortController().signal, assertCurrent: () => {} });

test('legacy scan reports unsupported rows without rewriting or silently dropping them', () => {
    const noSnapshot = legacy(); delete noSnapshot.draftState;
    const storage = storageFor([legacy(), { unknown: 'preserve' }, noSnapshot]);
    storage.setItem(collectionKey, '{malformed');
    const before = storage.getItem(draftsKey);
    const result = migration.scanLegacyProjects?.(storage);
    assert.ok(result, 'Legacy projects need a lossless migration reader');
    assert.equal(result.entries.length, 1);
    assert.equal(result.issues.length, 3);
    assert.equal(storage.getItem(draftsKey), before);
    assert.equal(storage.getItem(collectionKey), '{malformed');
});

test('migration preserves geometry and uploads only embedded images while keeping the local copy', async () => {
    const state = setup(); const source = entry(state.storage); const before = state.storage.getItem(draftsKey);
    const receipt = await migration.importLegacyProject(source, options(state));
    assert.equal(receipt.id, 42); assert.equal(state.creates, 1); assert.equal(state.uploads, 1);
    const saved = [...state.documents.values()][0];
    assert.deepEqual(saved.snapshot.modelBounds, { x: 150, y: 85, width: 600, height: 700 });
    assert.deepEqual(saved.snapshot.customization.modelImages, { front: { mediaId: 12 }, back: { mediaId: 12 } });
    assert.equal(saved.snapshot.customization.decorations[0].widthCm, 20.4);
    assert.equal(saved.snapshot.customization.decorations[0].image.mediaId, 100);
    assert.equal(saved.snapshot.customization.comment, 'Сохранить расположение');
    assert.equal(state.storage.getItem(draftsKey), before);
});

test('a retry after a lost committed POST recovers through a receipt without reuploading or overwriting edits', async () => {
    const state = setup(); const source = entry(state.storage); const create = state.transport.create;
    state.transport.create = async payload => { await create(payload); throw new TypeError('Response lost'); };
    await assert.rejects(migration.importLegacyProject(source, options(state)), TypeError);
    const saved = [...state.documents.values()][0]; saved.title = 'Изменён на другом устройстве'; saved.version = 2;
    const receipt = await migration.importLegacyProject(entry(state.storage), options(state));
    assert.equal(receipt.id, 42); assert.equal(receipt.title, 'Изменён на другом устройстве');
    assert.equal(receipt.version, 2); assert.equal(state.creates, 1); assert.equal(state.uploads, 1); assert.equal(state.products, 1);
});

test('migration key survives reload and distinguishes original record bytes and namespaces', async () => {
    const state = setup(); const original = await migration.legacyProjectKey(entry(state.storage));
    assert.match(original, /^legacy-v1-[a-f0-9]{64}$/);
    assert.equal(await migration.legacyProjectKey(entry(state.storage)), original);
    const changed = legacy(); changed.draftState.customization.comment = 'Другая версия';
    state.storage.setItem(draftsKey, JSON.stringify([changed]));
    assert.notEqual(await migration.legacyProjectKey(entry(state.storage)), original);
    state.storage.setItem(collectionKey, JSON.stringify([legacy()]));
    const other = migration.scanLegacyProjects(state.storage).entries.find(x => x.storageKey === collectionKey);
    assert.notEqual(await migration.legacyProjectKey(other), original);
});

test('cleanup preserves unknown raw JSON numbers and escaped delimiters without round trips', async () => {
    const storage = storageFor();
    const unknown = '{ "unrecognized":1e400,"id":9007199254740993,"text":"[,\\\" ] ,", "nested":[{"keep":true}] }';
    storage.setItem(draftsKey, `[ ${unknown}, ${JSON.stringify(legacy())}, false, null ]`);
    const state = setup(storage); const source = entry(storage);
    const receipt = await migration.importLegacyProject(source, options(state));
    assert.equal(await migration.removeImportedLegacyProject(source, receipt.id, options(state)), true);
    assert.equal(storage.getItem(draftsKey), `[${unknown},false,null]`);
});

test('source fingerprint distinguishes integers rounded to the same JavaScript number', async () => {
    const storage = storageFor();
    const raw = '{"opaque":9007199254740992,' + JSON.stringify(legacy()).slice(1);
    storage.setItem(draftsKey, `[${raw}]`);
    const state = setup(storage); const source = entry(storage);
    const originalKey = await migration.legacyProjectKey(source);
    const receipt = await migration.importLegacyProject(source, options(state));
    storage.setItem(draftsKey, `[${raw.replace('9007199254740992', '9007199254740993')}]`);
    assert.notEqual(await migration.legacyProjectKey(entry(storage)), originalKey);
    assert.equal(await migration.removeImportedLegacyProject(source, receipt.id, options(state)), false);
    assert.ok(storage.getItem(draftsKey).includes('9007199254740993'));
});

test('distinct literal UTF-16 surrogates cannot share a receipt or authorize cleanup of a changed source', async () => {
    const storage = storageFor();
    const raw = '{"opaque":"' + String.fromCharCode(0xd800) + '",' + JSON.stringify(legacy()).slice(1);
    storage.setItem(draftsKey, `[${raw}]`);
    const state = setup(storage); const original = entry(storage);
    const receipt = await migration.importLegacyProject(original, options(state));
    const changedRaw = raw.replace(String.fromCharCode(0xd800), String.fromCharCode(0xd801));
    storage.setItem(draftsKey, `[${changedRaw}]`);
    const changed = entry(storage);
    assert.notEqual(await migration.legacyProjectKey(changed), await migration.legacyProjectKey(original));
    await assert.rejects(migration.removeImportedLegacyProject(changed, receipt.id, options(state)));
    assert.equal(storage.getItem(draftsKey), `[${changedRaw}]`);
});

test('concurrent create conflict resolves the existing import, but a deleted import never resurrects', async () => {
    const state = setup(); const source = entry(state.storage); const create = state.transport.create;
    state.transport.create = async payload => { await create(payload); throw statusError(409); };
    assert.equal((await migration.importLegacyProject(source, options(state))).id, 42);
    state.transport.receipt = async () => { throw statusError(410); };
    await assert.rejects(migration.importLegacyProject(source, options(state)), error => error.status === 410);
    assert.equal(state.creates, 1);
});

test('unrelated image URLs are rejected before any upload or project creation', async () => {
    const item = legacy(); item.draftState.customization.modelImages.back = 'https://other.test/image.png';
    const state = setup(storageFor([item])); const before = state.storage.getItem(draftsKey);
    await assert.rejects(migration.importLegacyProject(entry(state.storage), options(state)));
    assert.equal(state.uploads, 0); assert.equal(state.creates, 0); assert.equal(state.storage.getItem(draftsKey), before);
});

test('account changes during POST prevent late success and local cleanup', async () => {
    const state = setup(); const source = entry(state.storage); const create = state.transport.create; let current = true;
    state.transport.create = async payload => { const result = await create(payload); current = false; return result; };
    const input = { ...options(state), assertCurrent: () => { if (!current) throw new DOMException('Account changed', 'AbortError'); } };
    await assert.rejects(migration.importLegacyProject(source, input), { name: 'AbortError' });
    assert.equal(JSON.parse(state.storage.getItem(draftsKey)).length, 1);
});

test('explicit cleanup requires a live matching receipt and preserves unknown and changed source rows', async () => {
    const state = setup(storageFor([{ unknown: 'keep' }, legacy(), { also: ['keep', 1] }]));
    const source = entry(state.storage); const receipt = await migration.importLegacyProject(source, options(state));
    assert.equal(await migration.removeImportedLegacyProject(source, receipt.id, options(state)), true);
    assert.deepEqual(JSON.parse(state.storage.getItem(draftsKey)), [{ unknown: 'keep' }, { also: ['keep', 1] }]);
    state.storage.setItem(draftsKey, JSON.stringify([legacy()]));
    const changed = legacy(); changed.name = 'Изменён локально';
    state.storage.setItem(draftsKey, JSON.stringify([changed]));
    assert.equal(await migration.removeImportedLegacyProject(source, receipt.id, options(state)), false);
    assert.deepEqual(JSON.parse(state.storage.getItem(draftsKey)), [changed]);
    state.transport.receipt = async () => null;
    await assert.rejects(migration.removeImportedLegacyProject(source, receipt.id, options(state)));
    assert.deepEqual(JSON.parse(state.storage.getItem(draftsKey)), [changed]);
});

test('a changed account after receipt verification never deletes its browser source', async () => {
    const state = setup(); const source = entry(state.storage); const receipt = await migration.importLegacyProject(source, options(state));
    let current = true; const lookup = state.transport.receipt;
    state.transport.receipt = async key => { const result = await lookup(key); current = false; return result; };
    await assert.rejects(migration.removeImportedLegacyProject(source, receipt.id, {
        ...options(state), assertCurrent: () => { if (!current) throw new DOMException('Account changed', 'AbortError'); },
    }), { name: 'AbortError' });
    assert.equal(JSON.parse(state.storage.getItem(draftsKey)).length, 1);
});
