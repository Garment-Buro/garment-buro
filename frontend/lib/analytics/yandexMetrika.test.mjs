import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

import {
    isYandexMetrikaHost,
    YANDEX_METRIKA_COUNTER_ID,
} from './yandexMetrika.ts';

const component = fs.readFileSync(
    path.join(process.cwd(), 'components', 'analytics', 'YandexMetrika.tsx'),
    'utf8',
);

test('Yandex Metrika is limited to the public production storefront', () => {
    assert.equal(YANDEX_METRIKA_COUNTER_ID, 112566503);
    assert.equal(isYandexMetrikaHost('garment-buro.ru'), true);
    assert.equal(isYandexMetrikaHost('www.garment-buro.ru'), true);
    assert.equal(isYandexMetrikaHost('dev.garment-buro.ru'), false);
    assert.equal(isYandexMetrikaHost('partner.garment-buro.ru'), false);
    assert.equal(isYandexMetrikaHost('production.garment-buro.ru'), false);
    assert.equal(isYandexMetrikaHost('widget.garment-buro.ru'), false);
});

test('SPA tracking queues one deferred hit per changed URL', () => {
    assert.match(component, /defer:\s*true/);
    assert.match(component, /ecommerce:\s*'dataLayer'/);
    assert.match(component, /'hit', url/);
    assert.match(component, /previousUrl\.current === url/);
});

