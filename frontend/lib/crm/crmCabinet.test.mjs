import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { spawnSync } from 'node:child_process';

const frontendRoot = process.cwd();
const readFrontend = (...parts) => fs.readFileSync(path.join(frontendRoot, ...parts), 'utf8');

test('CRM build fails without coordinated identity and accepts valid enabled or disabled configurations', () => {
    for (const [crm, identity, valid] of [['true', 'false', false], ['true', 'true', true], ['false', 'false', true]]) {
        const result = spawnSync(process.execPath, ['--disable-warning=MODULE_TYPELESS_PACKAGE_JSON', '--input-type=module', '-e', "await import('./next.config.ts')"], {
            cwd: frontendRoot,
            env: { ...process.env, NEXT_PUBLIC_CATALOG_WRITES_ENABLED: 'false', NEXT_PUBLIC_CRM_CABINET_ENABLED: crm, NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED: identity },
            encoding: 'utf8',
        });
        assert.equal(result.status === 0, valid);
        if (!valid) assert.match(result.stderr, /NEXT_PUBLIC_CRM_CABINET_ENABLED requires NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED/);
    }
});

test('CRM access and project reads use authenticated same-origin clients', () => {
    const authApi = readFrontend('lib', 'api', 'auth.ts');
    const crmApi = readFrontend('lib', 'api', 'crm.ts');
    const accessStore = readFrontend('store', 'identityAccessStore.ts');

    assert.match(authApi, /['"]\/auth\/access['"]/);
    assert.match(authApi, /Authorization:\s*`Bearer \$\{token\}`/);
    assert.match(crmApi, /`\/crm\/projects\?\$\{projectQueryString\(query\)\}`/);
    assert.match(crmApi, /Authorization:\s*`Bearer \$\{token\}`/);
    assert.match(accessStore, /runAuthenticated\(token => getAuthAccess\(token\)\)/);
    assert.match(accessStore, /error\.status === 401 \|\| error\.status === 403/);
    assert.doesNotMatch(accessStore, /persist\s*\(/);
});

test('CRM route and navigation stay closed until both build and RBAC gates pass', () => {
    const page = readFrontend('app', 'admin', 'crm', 'page.tsx');
    const shell = readFrontend('components', 'admin', 'AdminPageShell.tsx');
    const screen = readFrontend('components', 'admin', 'CrmProjectsScreen.tsx');

    assert.match(page, /if \(!isCrmCabinetEnabled\(\)\) notFound\(\)/);
    assert.match(shell, /crmEnabled\s*&&\s*hasCrmAccess/);
    assert.match(screen, /useCrmProjects\(identityAccess\.hasCrmAccess\)/);
    assert.match(screen, /нет доступа к производственному кабинету/);
});
