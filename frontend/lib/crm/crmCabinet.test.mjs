import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const frontendRoot = process.cwd();
const projectRoot = path.dirname(frontendRoot);
const readFrontend = (...parts) => fs.readFileSync(path.join(frontendRoot, ...parts), 'utf8');
const readProject = (...parts) => fs.readFileSync(path.join(projectRoot, ...parts), 'utf8');

test('CRM cabinet is a default-off build feature coupled to identity v2', () => {
    const authConfig = readFrontend('lib', 'auth', 'config.ts');
    const nextConfig = readFrontend('next.config.ts');
    const dockerfile = readFrontend('Dockerfile');
    const environment = readProject('.env.example');
    const compose = [
        readProject('docker-compose.yml'),
        readProject('docker-compose.local.yml'),
    ].join('\n');

    assert.match(authConfig, /NEXT_PUBLIC_CRM_CABINET_ENABLED\s*===\s*['"]true['"]/);
    assert.match(nextConfig, /CRM_CABINET_ENABLED\s*&&\s*!IDENTITY_SESSION_V2_ENABLED/);
    assert.match(dockerfile, /ARG NEXT_PUBLIC_CRM_CABINET_ENABLED=false/);
    assert.match(dockerfile, /ENV NEXT_PUBLIC_CRM_CABINET_ENABLED=/);
    assert.match(environment, /NEXT_PUBLIC_CRM_CABINET_ENABLED=false/);
    assert.equal(
        (compose.match(/NEXT_PUBLIC_CRM_CABINET_ENABLED:\s*\$\{/g) || []).length,
        2,
    );
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
