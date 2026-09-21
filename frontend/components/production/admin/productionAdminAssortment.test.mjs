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
const patterns = readFileSync(
    new URL('./assortment/AdminPatterns.tsx', import.meta.url),
    'utf8',
);
const models = readFileSync(
    new URL('./assortment/AdminModels.tsx', import.meta.url),
    'utf8',
);
const dialog = readFileSync(
    new URL('./assortment/AssortmentDialog.tsx', import.meta.url),
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
    assert.match(
        css,
        /\.assortmentDialog\s*\{[^}]*height:\s*calc\(100dvh - max\(16px, env\(safe-area-inset-top\)\)\)/s,
    );
    assert.match(css, /\.measureGrid\s*\{[^}]*repeat\(2, minmax\(0, 1fr\)\)/s);
    assert.match(
        css,
        /\.patternIdentityGrid,[\s\S]*\.patternMeasurements\s*\{[^}]*grid-template-columns:\s*1fr/s,
    );
});

test('pattern editor uses visual measurements and compact header controls', () => {
    assert.match(patterns, /type="range"/);
    assert.match(patterns, /step="2"/);
    assert.match(patterns, /className=\{styles\.patternFilePicker\}/);
    assert.match(patterns, /PDF, JPEG, PNG или WebP/);
    assert.match(patterns, /headerActions=/);
    assert.match(patterns, /name: editor\.code/);
    assert.doesNotMatch(patterns, />\s*Название\s*</);
    assert.doesNotMatch(patterns, /Ширина и длина должны попадать/);
    assert.match(dialog, />\s*Закрыть\s*</);
    assert.doesNotMatch(dialog, /PiX/);
});

test('model editor explains the flow and keeps one compact size editor open', () => {
    assert.match(models, /1\. Модель/);
    assert.match(models, /2\. Размеры/);
    assert.match(models, /3\. Диапазоны/);
    assert.match(models, /className=\{styles\.sizeCardList\}/);
    assert.match(models, /aria-selected=\{activeSizeIndex === index\}/);
    assert.match(models, /className=\{styles\.sizeDetailCard\}/);
    assert.match(models, /<SizeRangeEditor/);
    assert.match(models, /step="2"/);
    assert.doesNotMatch(models, /Сначала задайте общие параметры/);
});

test('assortment dialog scrolls below an opaque fixed header', () => {
    assert.match(dialog, /className=\{styles\.assortmentDialogBody\}/);
    assert.match(
        css,
        /\.assortmentDialog\s*\{[^}]*overflow:\s*hidden/s,
    );
    assert.match(
        css,
        /\.assortmentDialogBody\s*\{[^}]*overflow-y:\s*auto/s,
    );
    assert.doesNotMatch(
        css,
        /\.dialogHeading\s*\{[^}]*position:\s*sticky/s,
    );
});
