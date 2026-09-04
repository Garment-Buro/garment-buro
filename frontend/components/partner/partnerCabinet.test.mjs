import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const partnerRoot = path.join(root, 'components', 'partner');
const read = (file) => fs.readFileSync(path.join(partnerRoot, file), 'utf8');

const dashboardSource = read('PartnerDashboard.tsx');
const dashboardStyles = read('PartnerDashboard.module.css');
const financeSource = read('PartnerFinanceCard.tsx');
const requisitesSource = read('PartnerRequisitesCard.tsx');
const resourcesSource = read('PartnerResources.tsx');
const hookSource = fs.readFileSync(
    path.join(root, 'hooks', 'partner', 'usePartnerCabinet.ts'),
    'utf8',
);
const apiSource = fs.readFileSync(path.join(root, 'lib', 'api', 'partners.ts'), 'utf8');

test('partner cabinet uses a top context substrate with an overlapping control sheet', () => {
    assert.match(dashboardSource, /PartnerCabinetHeader/);
    assert.match(dashboardSource, /className=\{styles\.sheet\}/);
    assert.match(dashboardStyles, /\.sheet\s*\{[\s\S]*margin-top:\s*-48px/s);
    assert.match(dashboardStyles, /@media \(min-width:\s*960px\)[\s\S]*margin-top:\s*-64px/s);
    assert.match(dashboardStyles, /@media \(min-width:\s*640px\)/);
});

test('partner cabinet exposes only current financial and service actions', () => {
    assert.match(financeSource, /Доступно к выводу/);
    assert.match(financeSource, /Вывести деньги/);
    assert.match(requisitesSource, /Сохранить реквизиты/);
    assert.match(resourcesSource, /Правовые документы/);
    assert.match(resourcesSource, /Написать в поддержку/);
    assert.doesNotMatch(dashboardSource, /подписчик/i);
    assert.doesNotMatch(dashboardSource, /изменить название/i);
    assert.doesNotMatch(dashboardSource, /изменить описание/i);
});

test('partner requisites and payout requests use authenticated backend APIs', () => {
    assert.match(hookSource, /getPartnerRequisites/);
    assert.match(hookSource, /updatePartnerRequisites/);
    assert.match(hookSource, /createPartnerPayout/);
    assert.match(apiSource, /requestJson<PartnerRequisites \| null>\('\/partner\/requisites'/);
    assert.match(apiSource, /method:\s*'PUT'/);
});

test('partner cabinet has accessible interaction and reduced motion states', () => {
    assert.match(dashboardSource, /className=\{styles\.skipLink\}/);
    assert.match(requisitesSource, /aria-expanded=\{open\}/);
    assert.match(resourcesSource, /aria-controls="partner-documents"/);
    assert.match(dashboardStyles, /:focus-visible/);
    assert.match(dashboardStyles, /@media \(prefers-reduced-motion:\s*reduce\)/);
});
