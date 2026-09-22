import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (name) =>
    readFileSync(new URL(name, import.meta.url), 'utf8');

test('my work shows the full illustrated cycle without a terminal shortcut', () => {
    const source = read('./ProductionCycle.tsx');
    const css = read('./ProductionFlow.module.css');

    assert.doesNotMatch(source, /Открыть терминал роли/);
    for (const title of [
        'Проверка заказа',
        'Раскрой',
        'DTF',
        'Комплектовка',
        'Цех',
        'ВТО',
        'Упаковка',
        'Отправка',
    ]) {
        assert.match(source, new RegExp(`title: '${title}'`));
    }
    assert.match(source, /data-current=\{current\}/);
    assert.match(css, /\.cycleGrid\s*\{[^}]*repeat\(4,/s);
    assert.match(
        css,
        /@media \(max-width: 900px\)[\s\S]*\.cycleGrid\s*\{[^}]*repeat\(2,/s,
    );
});

test('bag history, order comments and cutting data follow role rules', () => {
    const bag = read('./ProductionBag.tsx');
    const journal = read('./ProductionJournal.tsx');
    const unit = read('../ProductionUnit.tsx');
    const cutting = read('../ProductionCuttingBrief.tsx');

    assert.match(bag, /\['tech', 'kit', 'packing'\]\.includes\(station\)/);
    assert.match(journal, /История мешка/);
    assert.match(unit, /Комментарий к заказу/);
    assert.match(unit, /station === 'cut'/);
    for (const label of [
        'Код лекала',
        'Ткань',
        'Где ткань',
        'Ширина спинки',
        'Длина изделия',
        'Длина рукава',
        'DTF',
    ]) {
        assert.match(cutting, new RegExp(label));
    }
});
