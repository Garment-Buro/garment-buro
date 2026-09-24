import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const types = readFileSync(
    new URL('../../../lib/production/adminTypes.ts', import.meta.url),
    'utf8',
);
const records = readFileSync(new URL('./AdminRecords.tsx', import.meta.url), 'utf8');
const table = readFileSync(new URL('./AdminRecordsTable.tsx', import.meta.url), 'utf8');
const editor = readFileSync(new URL('./AdminEmployeeEditor.tsx', import.meta.url), 'utf8');
const filtersPopup = readFileSync(new URL('./AdminFilters.tsx', import.meta.url), 'utf8');
const patterns = readFileSync(
    new URL('./assortment/AdminPatterns.tsx', import.meta.url),
    'utf8',
);
const terminal = readFileSync(
    new URL('./ProductionAdminTerminal.tsx', import.meta.url),
    'utf8',
);
const accessCode = readFileSync(
    new URL('./AdminEmployeeAccessCode.tsx', import.meta.url),
    'utf8',
);
const css = readFileSync(new URL('./ProductionAdmin.module.css', import.meta.url), 'utf8');

test('production admin separates employees from customer profiles', () => {
    assert.match(types, /\| 'employees'/);
    assert.match(types, /employees: 'Сотрудники'/);
    assert.doesNotMatch(types, /\| 'users'/);
    assert.doesNotMatch(records, /Здесь показаны сотрудники и тестовые доступы/);
    assert.match(records, /Добавить сотрудника/);
});

test('employee roles and one-time access code have dedicated controls', () => {
    assert.match(types, /export const employeeStations = \[/);
    assert.match(records, /AdminEmployeeEditor/);
    assert.match(records, /AdminEmployeeAccessCode/);
    assert.match(table, /onEmployee\(row\)/);
    assert.match(table, /Код не выдан/);
    assert.match(table, /'\*\*\*'/);
    assert.match(table, /onCode\(row\)/);
    assert.match(editor, /Менеджер/);
    assert.match(editor, /обычный личный код своего участка/);
    assert.match(editor, /employeeStations\.map/);
    assert.doesNotMatch(editor, /Нанесение|Пошив|ОТК/);
    assert.match(table, /row\.is_production_admin/);
});

test('employee creation makes optional fields clear and groups work settings', () => {
    assert.match(editor, /Фамилия \(необязательно\)/);
    assert.match(editor, /Телефон \(необязательно\)/);
    assert.match(editor, /Личные данные/);
    assert.match(editor, /Рабочий доступ/);
    assert.match(editor, /Участки производства/);
});

test('employee search, popup filters, and normal management are explicit', () => {
    assert.match(records, /код сотрудника/);
    assert.match(records, /availability/);
    assert.match(records, /station/);
    assert.match(records, /Болеет/);
    assert.match(records, /Любая роль/);
    assert.doesNotMatch(table, /row\.is_demo/);
    assert.doesNotMatch(table, /Управляется тестовым сценарием/);
    assert.doesNotMatch(table, /Личный код действует/);
    assert.doesNotMatch(editor, /Блокировка сразу отзывает код и текущие сессии/);
    assert.match(editor, /Работает/);
    assert.match(filtersPopup, /PiFunnel/);
    assert.match(filtersPopup, /role="dialog"/);
    assert.match(patterns, /<AdminFilters/);
    for (const section of [
        'orders',
        'payouts',
        'employees',
        'clients',
        'problems',
        'support',
    ]) {
        assert.match(records, new RegExp(`${section}: \\[`));
    }
    assert.match(records, /clientKindOptions/);
    assert.match(records, /key: 'sorting'/);
});

test('admin uses the compact cart animation asset', () => {
    assert.match(terminal, /logo_anim_cart\.mp4/);
    assert.doesNotMatch(terminal, /src="\/logo_anim\.mp4"/);
});

test('one-time code uses an adjacent svg copy control', () => {
    assert.match(accessCode, /className=\{styles\.accessCodeRow\}/);
    assert.match(accessCode, /className=\{styles\.copyCodeButton\}/);
    assert.match(accessCode, /<svg/);
    assert.match(accessCode, /navigator\.clipboard\.writeText/);
    assert.doesNotMatch(accessCode, /Скопировать код<\/button>/);
});

test('admin record tables become labeled cards on narrow screens', () => {
    assert.match(table, /data-label="Сотрудник"/);
    assert.match(table, /data-label="Покупатель"/);
    assert.match(table, /data-label="Партнёр"/);
    assert.match(css, /@media \(max-width: 720px\)[\s\S]*\.screen tbody tr/);
    assert.match(css, /content: attr\(data-label\)/);
    assert.match(table, /data-primary="true"/);
    assert.match(table, /data-action="true"/);
    assert.match(css, /\.filtersDialog[\s\S]*\.filterOptions/);
    assert.match(css, /\.toolbar > \.filterButton/);
});
