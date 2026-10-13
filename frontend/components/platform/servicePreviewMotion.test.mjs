import assert from 'node:assert/strict';
import test from 'node:test';
import { getPreviewPan } from './servicePreviewMotion.ts';

test('fitting or unmeasurable rails stay still', () => {
    for (const [viewport, content] of [[400, 300], [400, 400], [400, 402], [0, 500], [NaN, 500], [400, Infinity]]) {
        assert.equal(getPreviewPan(viewport, content), null);
    }
});

test('longer rails travel at the same slow speed without passing the last card', () => {
    assert.deepEqual(getPreviewPan(320, 400), { distance: 80, duration: 10000 });
    assert.deepEqual(getPreviewPan(320, 560), { distance: 240, duration: 30000 });
});
