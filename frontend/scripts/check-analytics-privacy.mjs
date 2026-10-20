/** Real standalone Next + Chromium. Optional --sdk /path runs an official SDK
 * snapshot; default adversarial fixture makes CI independent of vendor uptime.
 * Every vendor request is intercepted; no visit or synthetic data is published.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { chromium } from 'playwright';

const source = process.cwd();
const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'gb-analytics-privacy-'));
const marker = 'SYNTHETIC_PRIVATE_' + 'Q'.repeat(43);
const origin = 'https://garment-buro.ru';
const sdkIndex = process.argv.indexOf('--sdk');
const sdk = sdkIndex < 0 ? `(() => {
    const pending = Array.from(window.ym.a || [], args => Array.from(args));
    const read = fn => { try { return fn(); } catch (error) { return error.name; } };
    window.ym = (...args) => {
        if (args[1] !== 'hit') return;
        const payload = {args, parentDOM: read(() => parent.document.body.innerHTML),
            cookies: read(() => document.cookie), storage: read(() => localStorage.length),
            base: document.baseURI, referrer: document.referrer, location: location.href};
        fetch('https://mc.yandex.ru/watch/112566503?page-url=' + encodeURIComponent(args[2]), {
            method: 'POST', body: JSON.stringify(payload)
        }).catch(() => {});
    };
    // This would transmit a form ID if the SDK shared the application document.
    document.addEventListener('submit', event => {
        fetch('https://mc.yandex.ru/form?id=' + encodeURIComponent(event.target.id)).catch(() => {});
    });
    pending.forEach(args => window.ym(...args));
})();` : fs.readFileSync(process.argv[sdkIndex + 1], 'utf8');
let child, upstream, browser;

async function port() {
    const server = net.createServer();
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const value = server.address().port;
    await new Promise(resolve => server.close(resolve));
    return value;
}
function decoded(text) {
    for (let i = 0; i < 3; i++) { try { text = decodeURIComponent(text); } catch { break; } }
    return text;
}
async function eventually(check, message) {
    for (let i = 0; i < 150; i++) { if (await check()) return; await delay(50); }
    throw new Error(message);
}
async function run() {
    upstream = http.createServer((_request, response) => {
        response.writeHead(401, { 'Content-Type': 'application/json' });
        response.end(JSON.stringify({ detail: 'Fixture anonymous session' }));
    });
    await new Promise(resolve => upstream.listen(0, '127.0.0.1', resolve));
    const api = `http://127.0.0.1:${upstream.address().port}`;
    fs.cpSync(path.join(source, '.next/standalone'), folder, { recursive: true, dereference: true });
    fs.cpSync(path.join(source, '.next/static'), path.join(folder, '.next/static'), { recursive: true });
    fs.cpSync(path.join(source, 'public'), path.join(folder, 'public'), { recursive: true });
    // Owned loopback fixture replaces Docker DNS; route/policy/React code is unchanged.
    const manifest = path.join(folder, '.next/routes-manifest.json');
    const routes = JSON.parse(fs.readFileSync(manifest, 'utf8'));
    for (const group of Object.values(routes.rewrites)) {
        if (Array.isArray(group)) for (const route of group) {
            if (route.source === '/api/:path*') route.destination = api + '/api/:path*';
        }
    }
    fs.writeFileSync(manifest, JSON.stringify(routes));
    const serverPort = await port(), base = `http://127.0.0.1:${serverPort}`;
    child = spawn(process.execPath, ['server.js'], { cwd: folder, env: {
        PATH: process.env.PATH, NODE_ENV: 'production', NEXT_TELEMETRY_DISABLED: '1',
        PORT: String(serverPort), HOSTNAME: '127.0.0.1', INTERNAL_API_URL: api,
    }, stdio: 'ignore' });
    await eventually(async () => {
        assert.equal(child.exitCode, null, 'Standalone exited');
        try { return (await fetch(base + '/sw.js')).ok; } catch { return false; }
    }, 'Standalone not ready');
    const frameResponse = await fetch(base + '/analytics/frame');
    assert.equal(frameResponse.status, 200);
    assert.match(frameResponse.headers.get('content-security-policy'), /sandbox allow-scripts/);
    assert.equal(frameResponse.headers.get('referrer-policy'), 'no-referrer');
    const invalid = await fetch(base + '/analytics/frame?token=' + marker);
    assert.equal(invalid.status, 400);
    assert.equal((await invalid.text()).includes(marker), false);
    browser = await chromium.launch({ headless: true });
    // Playwright's serviceWorkers:block injects navigator.serviceWorker access
    // into every frame, which itself throws inside an opaque sandbox. Keep the
    // browser default; this gate intercepts every network request below.
    const context = await browser.newContext();
    const vendor = [], scripts = [], errors = [];
    await context.route('**/*', async route => {
        const request = route.request(), url = new URL(request.url());
        if (url.origin === origin) {
            if (url.pathname === '/sw.js') return route.abort();
            const response = await route.fetch({ url: base + url.pathname + url.search });
            return route.fulfill({ response });
        }
        const headers = await request.allHeaders();
        if (url.hostname === 'mc.yandex.ru' && url.pathname === '/metrika/tag.js') {
            scripts.push(headers);
            return route.fulfill({ contentType: 'application/javascript', body: sdk });
        }
        const body = request.postData() || '';
        assert.equal(decoded(request.url() + body + JSON.stringify(headers)).includes(marker), false,
            'Private marker reached a vendor request');
        vendor.push({ path: url.pathname, page: url.searchParams.get('page-url'), body });
        return route.fulfill({ headers: {
            'access-control-allow-origin': 'null', 'access-control-allow-credentials': 'true',
        }, contentType: 'application/json', body: JSON.stringify({ settings: { button_goals: 1, form_goals: 1 } }) });
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push({ name: error.name, sdk: error.stack?.includes('/metrika/tag.js') || false, message:error.message,stack:error.stack }));
    await page.goto(origin + '/profile?token=' + marker);
    await page.waitForFunction(() => document.body.dataset.browserSurface);
    await delay(100);
    assert.equal(scripts.length, 0, 'Private entry must not download SDK');
    assert.equal(await page.locator('iframe[title="Статистика просмотров"]').count(), 0);
    await page.goto(origin + '/contacts?project=' + marker + '#' + marker, {
        referer: 'https://example.invalid/' + marker,
    });
    await eventually(() => vendor.some(event => event.page === origin + '/contacts'), 'Public hit missing');
    assert.equal(await page.evaluate(() => typeof window.ym), 'undefined');
    assert.equal(await page.locator('script[src*="mc.yandex"]').count(), 0);
    const childFrame = page.frames().find(frame => frame !== page.mainFrame() && frame.url().includes('/analytics/frame'));
    assert.ok(childFrame, 'Isolated analytics document missing');
    const boundaries = await childFrame.evaluate(marker => {
        const result = {};
        for (const [key, read] of Object.entries({
            parentDOM: () => parent.document.body.innerHTML,
            cookies: () => document.cookie, storage: () => localStorage.length,
        })) { try { read(); result[key] = false; } catch (error) { result[key] = error.name === 'SecurityError'; } }
        result.cleanLocation = ![document.baseURI, document.referrer, location.href].some(value => value.includes(marker));
        return result;
    }, marker);
    assert.deepEqual(boundaries, { parentDOM: true, cookies: true, storage: true, cleanLocation: true });
    await page.evaluate(marker => {
        document.title = marker;
        const form = document.createElement('form'); form.id = marker; form.onsubmit = event => event.preventDefault();
        const input = document.createElement('input'); input.name = 'email'; input.value = marker;
        const submit = document.createElement('button'); submit.type = 'submit'; submit.textContent = 'Privacy fixture submit';
        form.append(input, submit); document.body.appendChild(form);
        const image = document.createElement('img'); image.src = '/api/design-media/' + marker + '/content'; document.body.appendChild(image);
    }, marker);
    await page.getByRole('button', { name: 'Privacy fixture submit' }).click();
    await delay(350);
    const before = vendor.length;
    // Real Next Link navigation keeps the root layout and frame alive.
    await page.locator('a[href="/delivery"]').first().click({ force: true });
    await eventually(() => vendor.some(event => event.page === origin + '/delivery'), 'SPA hit missing');
    assert.equal(scripts.length, 1, 'Public navigation downloaded another SDK');
    // Next integrates native history with usePathname/useSearchParams. Keep the
    // same document to prove the root effect removes a live frame on URL change.
    await page.evaluate(url => { window.__privacySameDocument = true; history.pushState(null, '', url); }, '/profile?token=' + marker);
    await eventually(async () => await page.locator('iframe[title="Статистика просмотров"]').count() === 0, 'Private SPA frame still active');
    assert.equal(await page.evaluate(() => window.__privacySameDocument), true);
    // Full private navigation also checks the fresh private entry again.
    await page.goto(origin + '/profile?token=' + marker);
    await page.waitForFunction(() => document.body.dataset.browserSurface);
    assert.equal(await page.locator('iframe[title="Статистика просмотров"]').count(), 0);
    await delay(150);
    assert.equal(scripts.length, 1);
    assert.ok(scripts.every(headers => !headers.referer), 'SDK request has a Referer');
    assert.equal(vendor.some(event => event.path === '/form'), false, 'Parent form reached SDK');
    if (sdkIndex >= 0) assert.ok(errors.every(error => error.sdk && error.name.includes('SecurityError')), JSON.stringify(errors));
    else assert.deepEqual(errors, []);
    assert.ok(before > 0);
    console.log(JSON.stringify({ standaloneNext: true, officialSdk: sdkIndex >= 0,
        privateEntryNoSdk: true, mainDocumentNoSdk: true, browserSandbox: boundaries,
        realSpaNavigation: true, privateSpaCleanup: true, oneSdkAcrossPublicNavigation: true, privateFormIsolated: true,
        noPrivateVendorMarkers: true, sdkReferrerAbsent: true, vendorRequests: vendor.length, containedSdkStorageErrors: errors.length }));
}
try { await run(); } finally {
    if (browser) await browser.close();
    if (child && child.exitCode === null && child.signalCode === null) {
        const exited = new Promise(resolve => child.once('exit', resolve)); child.kill('SIGTERM');
        await Promise.race([exited, delay(5000)]);
        if (child.exitCode === null && child.signalCode === null) { child.kill('SIGKILL'); await exited; }
    }
    if (upstream) await new Promise(resolve => upstream.close(resolve));
    fs.rmSync(folder, { recursive: true, force: true });
}
