import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const terminal = readFileSync(
    new URL('./ProductionTerminal.tsx', import.meta.url),
    'utf8',
);
const login = readFileSync(new URL('./ProductionLogin.tsx', import.meta.url), 'utf8');
const workspace = readFileSync(
    new URL('./workspaces/ProductionWorkspace.tsx', import.meta.url),
    'utf8',
);
const adminTerminal = readFileSync(
    new URL('./admin/ProductionAdminTerminal.tsx', import.meta.url),
    'utf8',
);
const legacyAdminRoute = readFileSync(
    new URL('../../app/production/admin/page.tsx', import.meta.url),
    'utf8',
);

test('production has one login form for employees and administrators', () => {
    assert.match(terminal, /if \(!authenticated\) return <ProductionLogin \/>/);
    assert.doesNotMatch(terminal, /mode === 'admin'/);
    assert.doesNotMatch(login, /Вход администратора/);
    assert.match(login, /6 цифр для сотрудника или 8 для/);
    assert.match(login, /pattern="\(\[0-9\]\{6\}\|99\[0-9\]\{6\}\)"/);
});

test('administrator is selected by the existing session role', () => {
    assert.match(terminal, /canAdminister && mode !== 'floor'/);
    assert.match(terminal, /<ProductionAdminTerminal key=\{userId\} \/>/);
    assert.match(workspace, /href="\/production"/);
    assert.doesNotMatch(workspace, /href="\/production\/admin"/);
});

test('old admin URL redirects to the shared production entry', () => {
    assert.match(legacyAdminRoute, /permanentRedirect\('\/production'\)/);
    assert.doesNotMatch(legacyAdminRoute, /ProductionTerminal/);
});

test('admin without a floor station does not get a dead production link', () => {
    assert.match(adminTerminal, /Boolean\(user\?\.stations\.length\)/);
    assert.match(workspace, /employee\.stations\.length === 0/);
    assert.match(workspace, /Нет назначенного участка/);
    assert.match(workspace, /Вернуться в админку/);
});
