import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';
import * as policy from './yandexMetrika.ts';

const compiled = ts.transpileModule(fs.readFileSync(new URL('./publicAnalyticsFrame.ts', import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText;
const compiledModule = { exports: {} };
vm.runInNewContext(compiled, { module: compiledModule, exports: compiledModule.exports, require(name) {
    assert.equal(name, './yandexMetrika'); return policy;
} });
const { createPublicAnalyticsFrame } = compiledModule.exports;
const docModule = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('./frameDocument.ts', import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText, { module: docModule, exports: docModule.exports, require: () => policy });
const html = docModule.exports.PUBLIC_ANALYTICS_FRAME_HTML;
const origin = 'https://garment-buro.ru';
const secret = 'SYNTHETIC_PRIVATE_' + 'Q'.repeat(43);
const plain = value => JSON.parse(JSON.stringify(value));

function fixture(initial = origin + '/') {
    const frames = [], listeners = new Map();
    const browser = {
        location: { href: initial },
        addEventListener: (name, callback) => listeners.set(name, callback),
        removeEventListener: name => listeners.delete(name),
    };
    const document = {
        createElement(tag) {
            assert.equal(tag, 'iframe');
            const frame = { attributes: {}, messages: [], removed: false,
                setAttribute(key, value) { this.attributes[key] = value; },
                remove() { this.removed = true; },
            };
            frame.contentWindow = { postMessage: (data, target) => frame.messages.push({ data: plain(data), target }) };
            return frame;
        },
        body: { appendChild: frame => frames.push(frame) },
    };
    const tracker = createPublicAnalyticsFrame(browser, document);
    return {
        tracker, frames, listeners,
        location(url) { browser.location.href = url; tracker.update(); },
        message(frame, type = 'gb-analytics-ready', source = frame.contentWindow, origin = 'null') {
            listeners.get('message')?.({ source, origin, data: { type } });
        },
    };
}

test('private/staging entry does not create or download an analytics frame', () => {
    for (const href of [origin + '/checkout?token=' + secret, 'https://dev.garment-buro.ru/']) {
        const f = fixture(href); f.tracker.update(); assert.equal(f.frames.length, 0);
        f.tracker.dispose(); assert.equal(f.listeners.size, 0);
    }
});

test('public frame has an opaque sandbox, no referrer and no main-document SDK', () => {
    const f = fixture(origin + '/?project=' + secret); f.tracker.update(); f.tracker.update();
    assert.equal(f.frames.length, 1);
    const frame = f.frames[0];
    assert.deepEqual(frame.attributes, { sandbox: 'allow-scripts', referrerpolicy: 'no-referrer', 'aria-hidden': 'true' });
    assert.equal(frame.hidden, true);
    assert.equal(frame.src, '/analytics/frame');
    assert.equal(frame.srcdoc, undefined);
    assert.equal(html.includes(secret), false);
    assert.ok(html.includes("frame-src 'none'"));
    assert.ok(html.includes('no-referrer'));
    assert.deepEqual(frame.messages, []);
    f.message(frame); f.message(frame);
    assert.deepEqual(frame.messages, [{ data: { type: 'gb-public-page', url: origin + '/' }, target: '*' }]);
    f.tracker.dispose(); assert.equal(frame.removed, true);
});

test('messages from other windows, origins and unknown types cannot make the frame ready', () => {
    const f = fixture(); f.tracker.update(); const frame = f.frames[0];
    f.message(frame, 'gb-analytics-ready', {}, 'null');
    f.message(frame, 'gb-analytics-ready', frame.contentWindow, origin);
    f.message(frame, 'unknown');
    assert.equal(frame.messages.length, 0);
    f.message(frame); assert.equal(frame.messages.length, 1);
    f.tracker.dispose();
});

test('SPA changes reuse one frame and send only distinct sanitized public URLs', () => {
    const f = fixture(); f.tracker.update(); const frame = f.frames[0]; f.message(frame);
    f.location(origin + '/?project=' + secret);
    f.location(origin + '/catalog?q=' + secret);
    f.location(origin + '/catalog#' + secret);
    f.location(origin + '/people/' + secret);
    assert.equal(f.frames.length, 1);
    assert.deepEqual(frame.messages.map(m => m.data.url), [origin + '/', origin + '/catalog', origin + '/people/profile']);
    assert.equal(JSON.stringify(frame.messages).includes(secret), false);
    f.tracker.dispose();
});

test('late ready notification rechecks private navigation and cannot revive an old frame', () => {
    const f = fixture(); f.tracker.update(); const old = f.frames[0];
    f.location(origin + '/constructor?project=' + secret); f.message(old);
    assert.equal(old.removed, true); assert.equal(old.messages.length, 0);
    f.location(origin + '/catalog'); const current = f.frames[1];
    f.message(old); assert.equal(current.messages.length, 0);
    f.message(current); assert.equal(current.messages[0].data.url, origin + '/catalog');
    f.tracker.dispose();
});

test('unmount and script failure remove the frame; a later update can retry', () => {
    const f = fixture(); f.tracker.update(); const old = f.frames[0];
    f.message(old, 'gb-analytics-unavailable'); assert.equal(old.removed, true);
    f.tracker.update(); assert.equal(f.frames.length, 2);
    f.tracker.dispose(); f.tracker.dispose(); f.tracker.update();
    assert.equal(f.frames.length, 2); assert.equal(f.frames[1].removed, true);
    assert.equal(f.listeners.size, 0);
});

test('child accepts only exact known pages from its parent and ignores supplied titles/parameters', () => {
    const listeners = new Map(), parent = {}, notifications = [], scripts = [];
    parent.postMessage = (...args) => notifications.push(args);
    const window = { addEventListener: (type, callback) => listeners.set(type, callback) };
    const document = { createElement: () => ({}), head: { appendChild: element => scripts.push(element) } };
    const inline = html.match(/<script>([\s\S]*)<\/script>/)[1];
    vm.runInNewContext(inline, { window, parent, document });
    assert.equal(scripts.length, 1);
    assert.equal(scripts[0].referrerPolicy, 'no-referrer');
    scripts[0].onload(); assert.equal(notifications[0][0].type, 'gb-analytics-ready');
    const message = (url, source = parent, origin_ = origin) => listeners.get('message')({
        source, origin: origin_, data: { type: 'gb-public-page', url, title: secret, params: { secret } },
    });
    message(origin + '/checkout'); message(origin + '/?token=' + secret);
    message(origin + '/', {}); message(origin + '/', parent, 'https://example.invalid');
    assert.equal(window.ym.a, undefined);
    message(origin + '/'); message(origin + '/'); message(origin + '/catalog');
    const calls = plain(window.ym.a.map(args => Array.from(args)));
    assert.equal(calls.length, 3);
    assert.equal(calls[0][1], 'init');
    for (const option of ['webvisor', 'clickmap', 'ecommerce', 'trackLinks', 'trackHash', 'accurateTrackBounce', 'sendTitle']) {
        assert.equal(calls[0][2][option], false, option);
    }
    assert.equal(calls[0][2].defer, true);
    assert.equal(calls[2][3].referer, origin + '/');
    assert.equal(calls[2][3].title, 'Каталог');
    assert.equal(JSON.stringify(calls).includes(secret), false);
});
