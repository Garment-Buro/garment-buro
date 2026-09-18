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
const accessCode = readFileSync(
    new URL('./AdminEmployeeAccessCode.tsx', import.meta.url),
    'utf8',
);
const css = readFileSync(new URL('./ProductionAdmin.module.css', import.meta.url), 'utf8');

test('production admin separates employees from customer profiles', () => {
    assert.match(types, /\| 'employees'/);
    assert.match(types, /employees: 'Сотрудники'/);
    assert.doesNotMatch(types, /\| 'users'/);
    assert.match(records, /Покупатели и их заказы[\s\S]*«Клиенты»/);
    assert.match(records, /Добавить сотрудника/);
});

test('employee roles and one-time access code have dedicated controls', () => {
    assert.match(types, /export const productionStations = \[/);
    assert.match(records, /AdminEmployeeEditor/);
    assert.match(records, /AdminEmployeeAccessCode/);
    assert.match(table, /onEmployee\(row\)/);
    assert.match(table, /Действующего кода нет/);
});

test('employee creation makes optional fields clear and groups work settings', () => {
    assert.match(editor, /Фамилия \(необязательно\)/);
    assert.match(editor, /Телефон \(необязательно\)/);
    assert.match(editor, /Личные данные/);
    assert.match(editor, /Рабочий доступ/);
    assert.match(editor, /Участки производства/);
});

test('employee search supports access codes and demo access is explicit', () => {
    assert.match(records, /код сотрудника/);
    assert.match(records, /по действующему личному[\s\S]*коду/);
    assert.match(table, /row\.is_demo/);
    assert.match(table, /Тестовый доступ/);
    assert.match(table, /Управляется тестовым сценарием/);
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
});
