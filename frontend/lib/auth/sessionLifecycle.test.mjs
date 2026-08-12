import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const frontendRoot = process.cwd();
const projectRoot = path.dirname(frontendRoot);
const readFrontend = (...parts) => fs.readFileSync(path.join(frontendRoot, ...parts), 'utf8');
const readProject = (...parts) => fs.readFileSync(path.join(projectRoot, ...parts), 'utf8');

test('session v2 remains guarded and is compiled into container builds explicitly', () => {
    const config = readFrontend('lib', 'auth', 'config.ts');
    const dockerfile = readFrontend('Dockerfile');
    const environment = readProject('.env.example');
    const compose = [
        readProject('docker-compose.yml'),
        readProject('docker-compose.local.yml'),
    ].join('\n');

    assert.match(config, /NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED\s*===\s*['"]true['"]/);
    assert.match(dockerfile, /ARG NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=false/);
    assert.match(dockerfile, /ENV NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=/);
    assert.match(environment, /NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=false/);
    assert.equal(
        (compose.match(/NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED:\s*\$\{/g) || []).length,
        2,
    );
});

test('v2 persists logout intent but never access tokens or user data', () => {
    const store = readFrontend('store', 'authStore.ts');
    const channel = readFrontend('lib', 'auth', 'sessionChannel.ts');

    assert.match(store, /sessionV2Enabled\s*\?\s*\{ logoutPending: state\.logoutPending \}/);
    assert.doesNotMatch(channel, /setItem\([^,]+,\s*(?:session|token|user)/);
    assert.match(channel, /setItem\(GENERATION_KEY, generation\)/);
});

test('app bootstrap and authenticated calls participate in the refresh lifecycle', () => {
    const layout = readFrontend('app', 'layout.tsx');
    const api = readFrontend('lib', 'api', 'auth.ts');
    const bootstrap = readFrontend('providers', 'AuthSessionBootstrap.tsx');
    const hooks = [
        readFrontend('hooks', 'auth', 'useAuthOrders.ts'),
        readFrontend('hooks', 'auth', 'useAuthSettings.ts'),
        readFrontend('hooks', 'auth', 'useEmailLinker.ts'),
    ];

    assert.match(layout, /<AuthSessionBootstrap\s*\/>/);
    assert.match(api, /['"]\/auth\/refresh['"]/);
    assert.match(api, /['"]\/auth\/session\/migrate['"]/);
    assert.match(api, /['"]\/auth\/logout['"]/);
    assert.match(bootstrap, /sessionRestorePending/);
    assert.match(bootstrap, /setInterval\(retry, 15_000\)/);
    hooks.forEach(source => assert.match(source, /runAuthenticated\(/));
});

test('catalog mutations preserve legacy mode and require coordinated auth in v2', () => {
    const catalogWrite = readFrontend('store', 'catalogWrite.ts');
    const config = readFrontend('lib', 'auth', 'config.ts');
    const nextConfig = readFrontend('next.config.ts');
    const dockerfile = readFrontend('Dockerfile');
    const environment = readProject('.env.example');
    const compose = [
        readProject('docker-compose.yml'),
        readProject('docker-compose.local.yml'),
    ].join('\n');
    const writeApis = [
        readFrontend('lib', 'api', 'products.ts'),
        readFrontend('lib', 'api', 'uploads.ts'),
        readFrontend('lib', 'api', 'settings.ts'),
        readFrontend('lib', 'api', 'options.ts'),
    ].join('\n');

    assert.match(catalogWrite, /if \(!isCatalogWritesV2Enabled\(\)\) return operation\(\)/);
    assert.match(catalogWrite, /runAuthenticated\(token => operation\(token\)\)/);
    assert.match(config, /NEXT_PUBLIC_CATALOG_WRITES_ENABLED\s*===\s*['"]true['"]/);
    assert.match(
        nextConfig,
        /CATALOG_WRITES_ENABLED\s*&&\s*!IDENTITY_SESSION_V2_ENABLED/,
    );
    assert.match(dockerfile, /ARG NEXT_PUBLIC_CATALOG_WRITES_ENABLED=false/);
    assert.match(environment, /NEXT_PUBLIC_CATALOG_WRITES_ENABLED=false/);
    assert.equal(
        (compose.match(/NEXT_PUBLIC_CATALOG_WRITES_ENABLED:\s*\$\{/g) || []).length,
        2,
    );
    assert.equal((writeApis.match(/bearerHeaders\(token\)/g) || []).length, 5);
});
