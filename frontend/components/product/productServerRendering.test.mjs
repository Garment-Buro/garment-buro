import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const serverPageSource = readFileSync(
    new URL('../../app/product/[id]/page.tsx', import.meta.url),
    'utf8',
);
const serverApiSource = readFileSync(
    new URL('../../lib/api/products.server.ts', import.meta.url),
    'utf8',
);
const clientPageSource = [
    new URL('./ProductPageClient.tsx', import.meta.url),
    new URL('../../hooks/product/useProductPage.ts', import.meta.url),
].map(file => readFileSync(file, 'utf8')).join('\n');

test('product route renders product data on the server with ISR', () => {
    assert.doesNotMatch(serverPageSource, /^['"]use client['"]/);
    assert.match(serverPageSource, /export const revalidate = 60/);
    assert.match(serverPageSource, /getServerProduct\(id\)/);
    assert.match(serverApiSource, /PRODUCT_REVALIDATE_SECONDS = 60/);
    assert.match(serverApiSource, /serverFetch\(`\/products\/\$\{productId\}`/);
    assert.match(serverPageSource, /initialProduct=\{product\}/);
    assert.match(serverPageSource, /generateMetadata/);
});

test('client product view starts from server data without an empty loading shell', () => {
    assert.match(clientPageSource, /useState<ProductData \| null>\(initialProduct\)/);
    assert.doesNotMatch(clientPageSource, /const \[loading, setLoading\]/);
    assert.doesNotMatch(clientPageSource, /setLoading\(true\)/);
    assert.doesNotMatch(clientPageSource, /Math\.random\(\)/);
});
