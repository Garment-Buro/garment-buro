import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const terminal = readFileSync(
    new URL('./ProductionAdminTerminal.tsx', import.meta.url),
    'utf8',
);
const types = readFileSync(
    new URL('../../../lib/production/adminTypes.ts', import.meta.url),
    'utf8',
);
const records = readFileSync(new URL('./AdminRecords.tsx', import.meta.url), 'utf8');
const table = readFileSync(new URL('./AdminRecordsTable.tsx', import.meta.url), 'utf8');
const details = readFileSync(new URL('./AdminInboxDetails.tsx', import.meta.url), 'utf8');
const css = readFileSync(new URL('./ProductionAdmin.module.css', import.meta.url), 'utf8');
const adminResource = readFileSync(
    new URL('../../../hooks/production/useAdminResource.ts', import.meta.url),
    'utf8',
);

test('admin navigation has separate problems and support tabs', () => {
    assert.match(types, /\| 'problems'/);
    assert.match(types, /\| 'support'/);
    assert.match(types, /problems: 'Проблемы'/);
    assert.match(types, /support: 'Поддержка'/);
    assert.match(terminal, /problems: PiWarningCircle/);
    assert.match(terminal, /support: PiLifebuoy/);
});

test('production and system administrators receive different sections', () => {
    assert.match(types, /productionAdminSections[\s\S]*'orders', 'problems'/);
    assert.match(types, /systemAdminSections[\s\S]*'support'/);
    assert.match(terminal, /user\?\.admin_scope === 'production'/);
    assert.match(terminal, /Производственный администратор/);
    assert.match(terminal, /Системный администратор/);
});

test('admin inbox lists filterable messages with distinct source context', () => {
    assert.match(records, /Любой приоритет/);
    assert.match(records, /Сообщения пользователей/);
    assert.match(records, /Сбои и препятствия на производстве/);
    assert.match(table, /priorityLabels\[row\.priority\]/);
    assert.match(table, /Ответственный №/);
    assert.match(table, /Проект №/);
});

test('admin can review and update an inbox record safely', () => {
    assert.match(details, /expected_version: item\.version/);
    assert.match(details, /method: 'PATCH'/);
    assert.match(details, /Внутренний комментарий/);
    assert.match(details, /Назначить на меня/);
    assert.match(details, /Пользователь и сотрудник этот комментарий не увидят/);
    assert.match(css, /\.inboxContext/);
    assert.match(css, /\.criticalBadge/);
});

test('admin lists refresh quietly while the tab is visible', () => {
    assert.match(records, /30_000/);
    assert.match(adminResource, /document\.visibilityState === 'visible'/);
    assert.match(adminResource, /hasCurrentData/);
});
