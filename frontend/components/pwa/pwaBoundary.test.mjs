import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const read = (...parts) => fs.readFileSync(path.join(root, ...parts), 'utf8');

const manifestSource = read('app', 'manifest.ts');
const partnerManifestSource = read('app', 'partner', 'manifest.webmanifest', 'route.ts');
const layoutSource = read('app', 'layout.tsx');
const constructorRouteSource = read('app', '[constructorRoute]', 'page.tsx');
const gateSource = read('components', 'pwa', 'PwaInstallGate.tsx');
const registrationSource = read('components', 'pwa', 'PwaRegistration.tsx');
const promptSource = read('lib', 'pwa', 'installPrompt.ts');
const serviceWorkerSource = read('public', 'sw.js');
const proxySource = read('proxy.ts');

test('the primary PWA launches the constructor while browser landings stay public', () => {
    assert.match(manifestSource, /id:\s*"\/constructor"/);
    assert.match(manifestSource, /start_url:\s*"\/constructor\?source=pwa"/);
    assert.match(manifestSource, /scope:\s*"\/"/);
    assert.match(constructorRouteSource, /PwaInstallGate/);
    assert.match(constructorRouteSource, /<PwaInstallGate returnHref=\{returnHref\}>/);
    assert.doesNotMatch(read('app', 'nikitamoiseev', 'page.tsx'), /PwaInstallGate/);
});

test('the constructor gate preserves the requested model and has platform install guidance', () => {
    assert.match(gateSource, /display-mode:\s*standalone/);
    assert.match(gateSource, /navigator as NavigatorWithStandalone/);
    assert.match(gateSource, /gb_pwa_pending_constructor/);
    assert.match(gateSource, /window\.location\.replace\(pendingPath\)/);
    assert.match(registrationSource, /beforeinstallprompt/);
    assert.match(registrationSource, /retainInstallPrompt/);
    assert.match(gateSource, /subscribeToInstallPrompt/);
    assert.match(promptSource, /let retainedPrompt/);
    assert.match(gateSource, /await installPrompt\.prompt\(\)/);
    assert.match(gateSource, /На экран Домой/);
    assert.match(gateSource, /Установить приложение/);
    assert.doesNotMatch(gateSource, /Продолжить в браузере/);
});

test('the service worker is registered only for production and never caches API data', () => {
    assert.match(layoutSource, /PwaRegistration/);
    assert.match(registrationSource, /process\.env\.NODE_ENV !== 'production'/);
    assert.match(registrationSource, /serviceWorker\.register\('\/sw\.js'/);
    assert.match(registrationSource, /updateViaCache:\s*'none'/);
    assert.match(serviceWorkerSource, /request\.mode === 'navigate'/);
    assert.match(serviceWorkerSource, /caches\.match\('\/offline\.html'\)/);
    assert.match(serviceWorkerSource, /url\.pathname\.startsWith\('\/api\/'\)/);
    assert.match(serviceWorkerSource, /url\.pathname\.startsWith\('\/storage\/'\)/);
});

test('the partner origin exposes a distinct installable PWA manifest', () => {
    assert.match(partnerManifestSource, /id:\s*'\/partner'/);
    assert.match(partnerManifestSource, /name:\s*'Garment Buro — партнёры'/);
    assert.match(partnerManifestSource, /start_url:\s*'\/partner'/);
    assert.match(partnerManifestSource, /scope:\s*'\/partner'/);
    assert.match(proxySource, /pathname === '\/manifest\.webmanifest'/);
    assert.match(proxySource, /url\.pathname = '\/partner\/manifest\.webmanifest'/);
    assert.match(proxySource, /PARTNER_PUBLIC_FILES/);
    assert.match(proxySource, /'\/sw\.js'/);
});
