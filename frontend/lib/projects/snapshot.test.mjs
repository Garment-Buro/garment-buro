import assert from 'node:assert/strict';
import test from 'node:test';
import { serializeProjectSnapshot, restoreProjectSnapshot } from './snapshot.ts';

const draft = () => ({
    activeView: 'back',
    canvasPixelSize: { width: 900, height: 900 },
    modelBounds: { x: 20, y: 35, width: 300, height: 400 },
    customization: {
        kind: 'constructor',
        selectedSize: 'M',
        modelImages: { front: '/front.webp', back: '/back.webp' },
        canvas: { widthCm: 90, heightCm: 90 },
        garment: { widthCm: 60, heightCm: 75 },
        fit: {
            selectedSize: 'M',
            sleeveMode: 'height',
            lengthCm: 75,
            widthCm: 60,
            lengthRange: { min: 60, max: 80 },
            widthRange: { min: 50, max: 70 },
        },
        totalPrice: 1234,
        comment: 'Мой проект',
        decorations: [
            {
                uid: 'text-one',
                variantId: 'custom_1',
                categoryId: 'prints',
                view: 'back',
                image: 'data:image/png;base64,AAAA',
                name: 'Текст',
                price: 200,
                widthCm: 18,
                heightCm: 12,
                x: -10.25,
                y: 80.5,
                scale: 1.25,
                rotation: -32,
                originalWidth: 900,
                originalHeight: 600,
                text: { content: 'Мой принт', fontId: 'manrope', fontSize: 32, color: '#ff3300' },
            },
        ],
    },
});

test('server snapshot preserves both views, text, fit and geometry while replacing every image with its media ID', async () => {
    const original = draft();
    original.customization.selectedColor = 'green';
    const before = structuredClone(original);
    const sources = [];
    const document = await serializeProjectSnapshot(original, async (source) => {
        sources.push(source);
        return { mediaId: sources.length };
    });
    assert.equal(document.schemaVersion, 1);
    assert.deepEqual(document.customization.modelImages, {
        front: { mediaId: 1 },
        back: { mediaId: 2 },
    });
    assert.deepEqual(document.customization.decorations[0].image, { mediaId: 3 });
    assert.equal(JSON.stringify(document).includes('data:image'), false);
    assert.deepEqual(original, before);
    const restored = restoreProjectSnapshot(document, [
        { id: 1, url: '/front.webp' },
        { id: 2, url: '/back.webp' },
        { id: 3, url: 'data:image/png;base64,AAAA' },
    ]);
    assert.deepEqual(restored, before);
});

test('shared image is resolved once and missing or conflicting media cannot silently restore a partial project', async () => {
    const original = draft();
    original.customization.modelImages.back = original.customization.modelImages.front;
    let calls = 0;
    const document = await serializeProjectSnapshot(original, async () => ({ mediaId: ++calls }));
    assert.equal(calls, 2);
    assert.throws(
        () => restoreProjectSnapshot(document, [{ id: 1, url: '/front.webp' }]),
        /image/i,
    );
    assert.throws(
        () =>
            restoreProjectSnapshot(document, [
                { id: 1, url: '/front.webp' },
                { id: 1, url: '/other.webp' },
                { id: 2, url: '/text.webp' },
            ]),
        /image/i,
    );
    await assert.rejects(
        serializeProjectSnapshot(original, async () => ({ mediaId: 0 })),
        RangeError,
    );
});

test('project transport keeps one authoritative mapping and does not duplicate the cart editor geometry', async () => {
    const original = draft();
    original.customization.geometry = { canvasPixelSize: original.canvasPixelSize, modelBounds: original.modelBounds };
    const before = structuredClone(original);
    const document = await serializeProjectSnapshot(original, async () => ({ mediaId: 42 }));
    assert.equal('geometry' in document.customization, false);
    assert.deepEqual(document.canvasPixelSize, original.canvasPixelSize);
    assert.deepEqual(document.modelBounds, original.modelBounds);
    assert.deepEqual(original, before);
    const restored = restoreProjectSnapshot(document, [{ id: 42, url: '/image.webp' }]);
    assert.deepEqual(restored.canvasPixelSize, original.canvasPixelSize);
    assert.deepEqual(restored.modelBounds, original.modelBounds);
});

test('image failure and cancellation do not produce a saveable document', async () => {
    const original = draft();
    await assert.rejects(
        serializeProjectSnapshot(original, async () => {
            throw new TypeError('Upload failed');
        }),
        TypeError,
    );
    const controller = new AbortController();
    let calls = 0;
    await assert.rejects(
        serializeProjectSnapshot(
            original,
            async () => {
                calls++;
                controller.abort();
                return { mediaId: 42 };
            },
            controller.signal,
        ),
        { name: 'AbortError' },
    );
    assert.equal(calls, 1);
});

test('nullable API metadata restores to optional editor fields and unknown schema versions are rejected', async () => {
    const document = await serializeProjectSnapshot(draft(), async () => ({ mediaId: 42 }));
    document.customization.fit = null;
    document.customization.comment = null;
    Object.assign(document.customization.decorations[0], {
        text: null,
        categoryId: null,
        originalWidth: null,
        originalHeight: null,
    });
    const restored = restoreProjectSnapshot(document, [{ id: 42, url: '/image.webp' }]);
    assert.equal('fit' in restored.customization, false);
    assert.equal('comment' in restored.customization, false);
    assert.equal('text' in restored.customization.decorations[0], false);
    assert.equal('originalWidth' in restored.customization.decorations[0], false);
    assert.throws(
        () =>
            restoreProjectSnapshot({ ...document, schemaVersion: 2 }, [
                { id: 42, url: '/image.webp' },
            ]),
        /version/i,
    );
});
