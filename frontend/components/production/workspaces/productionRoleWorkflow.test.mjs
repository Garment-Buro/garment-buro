import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (name) => readFileSync(new URL(name, import.meta.url), 'utf8');

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
    const actions = read('../BagActions.tsx');
    const journal = read('./ProductionJournal.tsx');
    const unit = read('../ProductionUnit.tsx');
    const cutting = read('../ProductionCuttingBrief.tsx');
    const views = read('./ProductionViews.tsx');

    assert.match(bag, /\['tech', 'kit', 'packing'\]\.includes\(station\)/);
    assert.match(journal, /История мешка/);
    assert.match(bag, /<strong>Комментарий к заказу<\/strong>/);
    assert.match(bag, /orderComments\.map/);
    assert.doesNotMatch(bag, /Версия<strong>/);
    assert.doesNotMatch(bag, /Печать QR мешка заказа/);
    assert.match(bag, /station !== 'tech'/);
    assert.match(bag, /const isOpen = opened === unit\.id/);
    assert.doesNotMatch(bag, /disabled=\{wide\}/);
    assert.match(actions, /Ждём подтверждение технолога/);
    assert.match(actions, /Ждём подтверждение DTF/);
    assert.match(actions, /<PiQrCode aria-hidden \/>/);
    assert.match(actions, /На комплектовку/);
    assert.match(actions, /Отправить в проблемы/);
    assert.match(unit, /station !== 'tech' && <OrderEvidence/);
    assert.match(unit, /canAct\(stations, 'kit'\)/);
    assert.doesNotMatch(unit, /Комплектность/);
    assert.match(views, /Макет заказчика/);
    assert.match(views, /Наложение на лекало/);
    assert.match(views, /Открыть оригинал лекала/);
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
