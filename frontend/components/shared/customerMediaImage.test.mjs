import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';
import { canOptimizePublicImage } from '../../lib/media/imagePolicy.ts';

const require = createRequire(import.meta.url);
const compiled = ts.transpileModule(fs.readFileSync(new URL('./CustomerMediaImage.tsx', import.meta.url), 'utf8'), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText;
const evaluated = { exports: {} };
new Function('require', 'exports', compiled)(name => name === '@/lib/media/imagePolicy' ? { canOptimizePublicImage } : require(name), evaluated.exports);
const image = props => renderToStaticMarkup(React.createElement(evaluated.exports.CustomerMediaImage, { alt: '', width: 64, height: 64, ...props }));

test('private design, API and signed project images render directly without public optimizer or referrer', () => {
    for (const src of ['/api/design-media/'+'x'.repeat(43)+'/content', '/api/profile/project-media/1/access', 'https://storage.test/projects/private.webp?X-Amz-Signature=private']) {
        const html = image({ src, unoptimized: false, referrerPolicy: 'unsafe-url' });
        assert.doesNotMatch(html, /\/_next\/image|srcSet/);
        assert.match(html, /referrerPolicy="no-referrer"/);
    }
});

test('public catalog images retain Next responsive optimization and caller layout', () => {
    const html = image({ src: '/uploads/product.webp', className: 'product-thumbnail' });
    assert.match(html, /\/_next\/image/);
    assert.match(html, /srcSet=/);
    assert.match(html, /class="product-thumbnail"/);
    assert.doesNotMatch(html, /referrerPolicy="no-referrer"/);
});
