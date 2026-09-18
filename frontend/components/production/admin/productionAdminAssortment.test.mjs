import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const terminal = readFileSync(
    new URL('./ProductionAdminTerminal.tsx', import.meta.url),
    'utf8',
);
const workspace = readFileSync(
    new URL('./AdminAssortment.tsx', import.meta.url),
    'utf8',
);
const types = readFileSync(
    new URL('../../../lib/production/assortmentTypes.ts', import.meta.url),
    'utf8',
);
const api = readFileSync(
    new URL('../../../lib/api/productionAssortment.ts', import.meta.url),
    'utf8',
);
const css = readFileSync(
    new URL('./ProductionAdmin.module.css', import.meta.url),
    'utf8',
);

test('admin exposes one product and warehouse workspace', () => {
    assert.match(terminal, /assortment: PiStorefront/);
    assert.match(terminal, /<AdminAssortment \/>/);
    for (const label of [
        'Модели',
        'Лекала',
        'Техкарты',
        'Ткани',
        'Фурнитура',
        'Коробки',
        'Товары',
    ]) {
        assert.match(types, new RegExp(label));
    }
    assert.match(workspace, /aria-label="Разделы товаров и склада"/);
});

test('assortment uses the shared production administrator session', () => {
    assert.match(api, /\/production\/admin\/assortment/);
    assert.doesNotMatch(api, /Authorization/);
    assert.match(api, /requestJson/);
    assert.match(api, /FormData/);
});

test('assortment remains usable on phones', () => {
    assert.match(css, /\.subnav\s*\{[^}]*overflow-x:\s*auto/s);
    assert.match(
        css,
        /\.assortmentCards,[\s\S]*grid-template-columns:\s*1fr/,
    );
    assert.match(css, /\.assortmentDialog\s*\{[^}]*min-height:\s*100dvh/s);
    assert.match(css, /\.measureGrid\s*\{[^}]*repeat\(2, minmax\(0, 1fr\)\)/s);
});
