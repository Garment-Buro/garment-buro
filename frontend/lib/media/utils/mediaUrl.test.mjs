import assert from 'node:assert/strict';
import test from 'node:test';

import { isVideoUrl, normalizeMediaUrl, parseMediaCsv } from './mediaUrl.ts';

test('media URLs share one normalization rule across admin forms and variants', () => {
    assert.equal(normalizeMediaUrl(' uploads/item.webp '), '/uploads/item.webp');
    assert.equal(normalizeMediaUrl('https://cdn.example/item.webp'), 'https://cdn.example/item.webp');
    assert.equal(normalizeMediaUrl(''), '');
    assert.deepEqual(parseMediaCsv('one.webp, /two.webp'), ['/one.webp', '/two.webp']);
});

test('video media detection supports product video formats with query strings', () => {
    assert.equal(isVideoUrl('/video/product.mp4?v=2'), true);
    assert.equal(isVideoUrl('/image/product.webp'), false);
});
