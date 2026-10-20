import assert from 'node:assert/strict';
import test from 'node:test';
import {
    LEGACY_CONSTRUCTOR_DRAFTS_STORAGE_KEY as draftsKey,
    LEGACY_COLLECTION_STORAGE_KEY as collectionKey,
    isLegacyProjectRecord,
    readLegacyConstructorDraft,
} from './legacyRecords.ts';

// Literal historical data, independent of the removed writer implementation.
const legacyRecord = () => ({
    id: 'draft-1783188000000-27', kind: 'draft', number: '003',
    name: 'Старый проект', imageSrc: '/uploads/front.png', productId: 27, savedAt: 1783188000000,
    draftState: {
        activeView: 'back', canvasPixelSize: { width: 640, height: 600 },
        modelBounds: { x: 90, y: 70, width: 460, height: 520 },
        customization: {
            kind: 'constructor', selectedSize: 'M',
            modelImages: { front: '/uploads/front.png', back: '/uploads/back.png' },
            canvas: { widthCm: 100, heightCm: 90 }, garment: { widthCm: 58, heightCm: 70 },
            decorations: [{
                view: 'back', uid: 'item_1', variantId: 'print_1', name: 'print',
                price: 300, image: '/mock/prints/1.webp', widthCm: 20, heightCm: 14,
                x: 320, y: 280, scale: 1.2, rotation: 25,
            }],
            totalPrice: 5300, comment: 'Не менять старый снимок',
        },
    },
});

function withWindow(value, run) {
    const previous = Object.getOwnPropertyDescriptor(globalThis, 'window');
    Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value });
    try { run(); }
    finally {
        if (previous) Object.defineProperty(globalThis, 'window', previous);
        else delete globalThis.window;
    }
}

test('historical storage namespaces remain literal for existing browser records', () => {
    assert.equal(draftsKey, 'plus2opacity-constructor-drafts');
    assert.equal(collectionKey, 'plus2opacity-my-collection');
});

test('historical geometry, numbering, decoration URLs and price snapshots remain readable', () => {
    const record = legacyRecord();
    assert.equal(isLegacyProjectRecord(record), true);
    const copy = structuredClone(record);
    assert.equal(isLegacyProjectRecord({ ...record, kind: 'collection' }), true);
    assert.deepEqual(record, copy);
});

test('unsupported historical rows and malformed snapshots are rejected without mutation', () => {
    for (const record of [null, [], { id: 12 }, { ...legacyRecord(), productId: '27' }, {
        ...legacyRecord(), draftState: { ...legacyRecord().draftState, canvasPixelSize: { width: '640', height: 600 } },
    }]) {
        const copy = structuredClone(record);
        assert.equal(isLegacyProjectRecord(record), false);
        assert.deepEqual(record, copy);
    }
});

test('an old constructor URL reads only its exact record and never rewrites unknown source data', () => {
    const record = legacyRecord();
    const raw = `[ {"unknown":9007199254740993}, ${JSON.stringify(record)}, null ]`;
    const reads = [], writes = [];
    withWindow({ localStorage: {
        getItem: key => { reads.push(key); return raw; },
        setItem: (...args) => { writes.push(args); throw new Error('Unexpected local write'); },
        removeItem: (...args) => { writes.push(args); throw new Error('Unexpected local removal'); },
    } }, () => {
        assert.deepEqual(readLegacyConstructorDraft(record.id), record);
        assert.equal(readLegacyConstructorDraft('other-id'), undefined);
    });
    assert.deepEqual(reads, [draftsKey, draftsKey]);
    assert.deepEqual(writes, []);
    assert.ok(raw.includes('9007199254740993'));
});

test('empty IDs and SSR never access browser storage', () => {
    withWindow({ get localStorage() { throw new Error('Unexpected read'); } }, () => {
        assert.equal(readLegacyConstructorDraft(null), undefined);
        assert.equal(readLegacyConstructorDraft(undefined), undefined);
        assert.equal(readLegacyConstructorDraft(''), undefined);
    });
    withWindow(undefined, () => assert.equal(readLegacyConstructorDraft('old-id'), undefined));
});

test('reading an old draft tolerates blocked browser storage without changing any record', () => {
    const denied = () => { throw new DOMException('Storage denied', 'SecurityError'); };
    for (const browser of [{ get localStorage() { return denied(); } }, { localStorage: { getItem: denied } }]) {
        withWindow(browser, () => assert.equal(readLegacyConstructorDraft('draft-100-27'), undefined));
    }
});

test('malformed and non-array historical storage cannot crash the reader or be repaired implicitly', () => {
    for (const raw of [null, '', 'not json', '{}', 'null', '[{"id":"broken"}]']) {
        let writes = 0;
        withWindow({ localStorage: { getItem: () => raw, setItem: () => { writes++; } } }, () => {
            assert.equal(readLegacyConstructorDraft('broken'), undefined);
        });
        assert.equal(writes, 0);
    }
});
