/** Real standalone Next/Chromium; synthetic history transport. SQL/RBAC covered by pytest. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { chromium } from 'playwright';

const source = process.cwd(), folder = fs.mkdtempSync(path.join(os.tmpdir(), 'gb-client-history-'));
let browser, child, upstream, page;
const reads = [], held = [], errors = [];
const state = { session: true, failAppend: false, invalidCursor: false, hold: false, failProfile: false };
const client = { key: 'user:3', user_id: 3, name: 'Клиент истории', email: 'client@example.test', phone: null,
    last_order_id: 1130, last_order_at: '2025-01-01T00:00:00Z', orders_count: 130, orders_total: '10400.00', paid_orders_total: '0.00' };
const orders = Array.from({ length: 130 }, (_, i) => ({ id: 1130 - i, created_at: '2025-01-01T00:00:00Z', total: '80.00',
    status: 'new', payment_status: 'pending', workflow_state: null, delivery_city: null, delivery_method: null, payment_method: null }));
const tickets = orders.map(order => ({ id: order.id, subject: `Обращение ${order.id}`, order_id: order.id,
    status: 'new', priority: 'normal', created_at: order.created_at, updated_at: order.created_at }));
const json = (response, value, status = 200) => { response.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });response.end(JSON.stringify(value)); };
const port = async () => { const server = net.createServer();await new Promise(ok => server.listen(0, '127.0.0.1', ok));const value = server.address().port;await new Promise(ok => server.close(ok));return value; };
async function until(check, message) { for (let i = 0; i < 200; i++) { if (await check()) return;await delay(50); }throw new Error(message); }
try {
    upstream = http.createServer((request, response) => {
        const url = new URL(request.url, 'https://fixture.invalid'), key = url.pathname;
        if (key === '/api/production/me') return state.session
            ? json(response, { id: 7, name: 'Администратор', stations: [], can_administer: true, admin_scope: 'system' }) : json(response, { detail: 'Signed out' }, 401);
        if (key === '/api/production/auth/logout') { state.session = false;return json(response, {}); }
        if (key === '/api/auth/refresh') return json(response, { detail: 'Signed out' }, 401);
        if (key === '/api/production/admin/stats') return json(response, { as_of: '2025-01-01T00:00:00Z', week_change: {}, order_states: [], payout_states: [] });
        if (key === '/api/production/admin/clients') return json(response, { items: [client], next_offset: null });
        if (key === '/api/production/admin/clients/detail') return state.failProfile
            ? json(response, { detail: 'Ошибка данных клиента' }, 503)
            : json(response, { ...client, tickets_count: 130, account: null, recipient: { patronymic: null, city: null, address: null, delivery_method: null, pickup_point: null } });
        if (key === '/api/production/admin/clients/orders' || key === '/api/production/admin/clients/tickets') {
            const kind = key.endsWith('/orders') ? 'orders' : 'tickets', query = Object.fromEntries(url.searchParams);
            assert.equal(query.limit, '24');assert.equal(query.key, 'user:3');reads.push({ kind, ...query });
            const send = () => {
                if (query.cursor && state.invalidCursor) return json(response, { detail: { code: 'invalid_cursor' } }, 422);
                if (query.cursor && state.failAppend) return json(response, { detail: 'Ошибка продолжения истории' }, 503);
                const offset = Number(query.cursor ?? 0), rows = kind === 'orders' ? orders : tickets;
                return json(response, { items: rows.slice(offset, offset + 24), next_cursor: rows.length > offset + 24 ? String(offset + 24) : null });
            };
            if (state.hold) held.push(send);else send();return;
        }
        return json(response, { detail: 'Unused fixture endpoint' }, 404);
    });
    await new Promise(ok => upstream.listen(0, '127.0.0.1', ok));
    const api = `http://127.0.0.1:${upstream.address().port}`;
    fs.cpSync(path.join(source, '.next/standalone'), folder, { recursive: true, dereference: true });
    fs.cpSync(path.join(source, '.next/static'), path.join(folder, '.next/static'), { recursive: true });
    fs.cpSync(path.join(source, 'public'), path.join(folder, 'public'), { recursive: true });
    const manifestFile = path.join(folder, '.next/routes-manifest.json'), manifest = JSON.parse(fs.readFileSync(manifestFile, 'utf8'));
    for (const group of Object.values(manifest.rewrites)) if (Array.isArray(group)) for (const route of group) if (route.source === '/api/:path*') route.destination = api + '/api/:path*';
    fs.writeFileSync(manifestFile, JSON.stringify(manifest));
    const base = `http://127.0.0.1:${await port()}`;
    child = spawn(process.execPath, ['server.js'], { cwd: folder, env: { PATH: process.env.PATH, NODE_ENV: 'production', NEXT_TELEMETRY_DISABLED: '1', PORT: new URL(base).port, HOSTNAME: '127.0.0.1', INTERNAL_API_URL: api }, stdio: 'ignore' });
    await until(async () => { assert.equal(child.exitCode, null);try { return (await fetch(base + '/sw.js')).ok; } catch { return false; } }, 'Standalone startup failed');
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ serviceWorkers: 'block' });page = await context.newPage();page.setDefaultTimeout(10000);
    await context.addInitScript(() => localStorage.setItem('cookieConsent', 'accepted'));
    await context.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort());
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + '/production');await page.getByRole('button', { name: 'Клиенты', exact: true }).click();
    const open = () => page.getByRole('button', { name: /Клиент истории/ }).click();
    state.failProfile = true;await open();
    await page.getByRole('alert').filter({ hasText: 'Ошибка данных клиента' }).waitFor();state.failProfile = false;
    await page.getByRole('button', { name: 'Повторить загрузку данных', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Клиент истории', exact: true });
    await dialog.getByRole('tab', { name: /Заказы 130/ }).waitFor();
    assert.equal(reads.length, 0, 'Profile must not prefetch histories');
    await dialog.getByRole('tab', { name: /Заказы/ }).click();
    await dialog.getByText('Показано 24 из 130', { exact: true }).waitFor();
    assert.equal(reads.filter(row => row.kind === 'tickets').length, 0);
    state.failAppend = true;await dialog.getByRole('button', { name: 'Ещё заказы', exact: true }).click();
    await dialog.getByRole('alert').filter({ hasText: 'Ошибка продолжения' }).waitFor();
    assert.equal(await dialog.locator('[role="tabpanel"] button').filter({ hasText: 'Заказ №' }).count(), 24);
    state.failAppend = false;await dialog.getByRole('button', { name: 'Повторить загрузку', exact: true }).click();
    await dialog.getByText('Показано 48 из 130', { exact: true }).waitFor();
    state.invalidCursor = true;await dialog.getByRole('button', { name: 'Ещё заказы', exact: true }).click();
    await dialog.getByRole('button', { name: 'Обновить историю', exact: true }).waitFor();state.invalidCursor = false;
    await dialog.getByRole('button', { name: 'Обновить историю', exact: true }).click();
    await dialog.getByText('Показано 24 из 130', { exact: true }).waitFor();
    await dialog.getByRole('tab', { name: 'Новый тикет', exact: true }).click();
    await dialog.getByLabel('Тема', { exact: true }).fill('Мой черновик');
    const select = dialog.getByRole('combobox');
    await select.selectOption('1130');
    while (await dialog.getByRole('button', { name: 'Ещё заказы для выбора', exact: true }).count()) {
        const before = await select.getByRole('option').count();await dialog.getByRole('button', { name: 'Ещё заказы для выбора', exact: true }).click();
        await until(async () => await select.getByRole('option').count() > before, 'Order picker continuation failed');
    }
    assert.equal(await select.getByRole('option').count(), 131);assert.equal(await select.inputValue(), '1130');
    assert.equal(await dialog.getByLabel('Тема', { exact: true }).inputValue(), 'Мой черновик');await select.selectOption('1001');
    for (const [width, height] of [[320, 850], [390, 850], [736, 390], [1280, 850]]) {
        await page.setViewportSize({ width, height });assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `Overflow at ${width}`);
    }
    if (process.env.GB_CLIENT_PROOF_DIR) await dialog.screenshot({ path: path.join(process.env.GB_CLIENT_PROOF_DIR, 'client-history-order-picker.png'), animations: 'disabled' });
    await dialog.getByRole('tab', { name: /Обращения/ }).click();await dialog.getByText('Показано 24 из 130', { exact: true }).waitFor();
    while (await dialog.getByRole('button', { name: 'Ещё обращения', exact: true }).count()) {
        const before = await dialog.locator('[role="tabpanel"] button').filter({ hasText: 'Обращение ' }).count();
        await dialog.getByRole('button', { name: 'Ещё обращения', exact: true }).click();
        await until(async () => await dialog.locator('[role="tabpanel"] button').filter({ hasText: 'Обращение ' }).count() > before, 'Ticket continuation failed');
    }
    await dialog.getByText('Показано 130 из 130', { exact: true }).waitFor();
    // Late private data after closing cannot reopen or populate another dialog.
    await dialog.getByRole('button', { name: 'Закрыть данные клиента', exact: true }).click();
    state.hold = true;await open();await page.getByRole('tab', { name: /Заказы/ }).click();
    await until(() => held.length === 1, 'History request was not held');
    await page.getByRole('button', { name: 'Закрыть данные клиента', exact: true }).click();
    state.hold = false;held.splice(0).forEach(send => send());await open();
    await page.getByRole('tab', { name: /Заказы 130/ }).waitFor();
    assert.equal(await page.getByRole('button', { name: /Заказ №/ }).count(), 0);
    state.hold = true;await page.getByRole('tab', { name: /Заказы/ }).click();await until(() => held.length === 1, 'Logout request was not held');
    const other = await context.newPage();await other.goto(base + '/production');
    await other.getByRole('button', { name: 'Выйти', exact: true }).click();await page.getByRole('heading', { name: 'Вход в терминал', exact: true }).waitFor();
    state.hold = false;held.splice(0).forEach(send => send());await delay(150);assert.equal(await page.getByRole('dialog').count(), 0);
    assert.deepEqual(errors, []);
    const proof = { standaloneNext: true, syntheticTransport: true, historyCount: 130, firstPage: 24, lazyTabs: true, appendRetry: true,
        profileRetry: true, cursorRecovery: true, orderPickerPast100: true, draftAndSelectionPreserved: true, ticketsPast100: true, lateCloseIgnored: true,
        lateLogoutIgnored: true, widths: [320, 390, 736, 1280], pageErrors: errors, requests: reads.length };
    if (process.env.GB_CLIENT_PROOF_DIR) fs.writeFileSync(path.join(process.env.GB_CLIENT_PROOF_DIR, 'client-history-browser.json'), JSON.stringify(proof, null, 2));
    console.log(JSON.stringify(proof));
} catch (error) {
    console.error('Client history browser gate failed:', error.message, await page?.locator('body').innerText().then(text => text.slice(-2000)).catch(() => '<closed>'));throw error;
} finally {
    held.splice(0).forEach(send => send());await browser?.close();
    if (child && child.exitCode === null) { child.kill('SIGTERM');await new Promise(ok => child.once('exit', ok)); }
    if (upstream) { upstream.closeAllConnections();await new Promise(ok => upstream.close(ok)); }
    fs.rmSync(folder, { recursive: true, force: true });
}
