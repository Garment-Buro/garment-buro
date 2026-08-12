import assert from 'node:assert/strict';
import test from 'node:test';

import {
    assertSupportedMediaFile,
    IMAGE_FILE_ACCEPT,
    isSupportedImageFile,
} from './upload.ts';

test('media upload accepts raster images and rejects SVG', () => {
    assert.equal(isSupportedImageFile({ type: 'image/webp' }), true);
    assert.equal(isSupportedImageFile({ type: 'image/svg+xml' }), false);
    assert.match(IMAGE_FILE_ACCEPT, /image\/webp/);
    assert.doesNotMatch(IMAGE_FILE_ACCEPT, /svg/);
    assert.throws(
        () => assertSupportedMediaFile({ type: 'image/svg+xml' }),
        /SVG/,
    );
});
