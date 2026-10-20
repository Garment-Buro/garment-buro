import assert from 'node:assert/strict';
import test from 'node:test';
import { createRequire } from 'node:module';
import { canOptimizePublicImage, publicImageLocalPatterns } from './imagePolicy.ts';

const require = createRequire(import.meta.url);
const { hasLocalMatch } = require('next/dist/shared/lib/match-local-pattern');
const config = (await import('../../next.config.ts')).default;

test('the installed Next optimizer permits public assets and rejects API and signed sources', () => {
    assert.deepEqual(config.images.localPatterns, publicImageLocalPatterns);
    for (const source of ['/landing-bg.webp', '/service-home/background.webp', '/nikitamoiseev/hoodie.png', '/uploads/модель.webp', '/_next/static/media/image.123.png']) {
        assert.equal(canOptimizePublicImage(source), true, source);
        assert.equal(hasLocalMatch(config.images.localPatterns, source), true, source);
    }
    for (const source of ['/api/design-media/'+'x'.repeat(43)+'/content', '/api/profile/project-media/1/access', '/storage/private/print.png', '/uploads/../api/design-media/x/content', '/uploads/%2e%2e/api/design-media/x/content', '/uploads/print.png?X-Amz-Signature=private', '/uploads/print.png?v=1']) {
        assert.equal(canOptimizePublicImage(source), false, source);
        assert.equal(hasLocalMatch(config.images.localPatterns, source), false, source);
    }
});

test('direct customer image policy also rejects encoded separators, external, inline and malformed sources', () => {
    for (const source of ['/uploads/%2e%2e%2fapi/design-media/x/content', '/uploads/%255capi', '//other.test/image.png', '/\\other.test/image.png', 'https://cdn.test/public.png', 'data:image/png;base64,YQ==', 'blob:http://localhost/id', '/uploads/image.png#token', '/uploads/%']) {
        assert.equal(canOptimizePublicImage(source), false, source);
    }
});
