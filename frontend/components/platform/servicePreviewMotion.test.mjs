import assert from 'node:assert/strict';
import test from 'node:test';
import { getPreviewPan } from './servicePreviewMotion.ts';

test('empty or unmeasurable sequences stay still', () => {
    for (const [viewport, cycle] of [[400, 0], [400, -10], [0, 500], [NaN, 500], [400, Infinity]]) {
        assert.equal(getPreviewPan(viewport, cycle), null);
    }
});

test('each pass travels one complete sequence at eight pixels per second', () => {
    assert.deepEqual(getPreviewPan(320, 400, 'left'), { from: -400, to: -800, duration: 50000, copies: 4 });
    assert.deepEqual(getPreviewPan(320, 560, 'left'), { from: -560, to: -1120, duration: 70000, copies: 4 });
});

test('opposite motion starts at the repeated sequence and keeps the same speed', () => {
    assert.deepEqual(getPreviewPan(320, 400, 'right'), { from: -800, to: -400, duration: 50000, copies: 4 });
});

test('short sequences repeat enough times to fill a wide viewport throughout the loop', () => {
    const loop = getPreviewPan(1000, 200, 'left');
    assert.equal(loop.copies, 8);
    assert.ok((loop.copies - 2) * 200 > 1000);
});
