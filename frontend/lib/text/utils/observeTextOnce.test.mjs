import assert from 'node:assert/strict';
import test from 'node:test';
import { observeTextOnce } from './observeTextOnce.ts';

function visibility(t) {
    const instances = [];
    const original = globalThis.IntersectionObserver;
    globalThis.IntersectionObserver = class {
        constructor(callback) { this.callback = callback; this.disconnections = 0; instances.push(this); }
        observe(target) { this.target = target; }
        disconnect() { this.disconnections += 1; }
        deliver(entries) { this.callback(entries); }
    };
    t.after(() => { globalThis.IntersectionObserver = original; });
    return () => instances[0];
}

test('a text reveal waits for its own visible intersection and runs only once', t => {
    const instance = visibility(t), target = {}, unrelated = {};
    let reveals = 0;
    const cleanup = observeTextOnce(target, () => { reveals += 1; });
    assert.equal(instance().target, target);
    instance().deliver([{ target, isIntersecting: false }, { target: unrelated, isIntersecting: true }]);
    assert.equal(reveals, 0);
    instance().deliver([{ target, isIntersecting: true }]);
    assert.equal(reveals, 1);
    assert.equal(instance().disconnections, 1);
    instance().deliver([{ target, isIntersecting: true }]);
    assert.equal(reveals, 1);
    cleanup();
});

test('cleanup prevents a queued intersection callback from revealing removed text', t => {
    const instance = visibility(t), target = {};
    let reveals = 0;
    const cleanup = observeTextOnce(target, () => { reveals += 1; });
    cleanup();
    instance().deliver([{ target, isIntersecting: true }]);
    assert.equal(reveals, 0);
    assert.equal(instance().disconnections, 1);
});

test('a browser without IntersectionObserver still reveals text', t => {
    const original = globalThis.IntersectionObserver;
    globalThis.IntersectionObserver = undefined;
    t.after(() => { globalThis.IntersectionObserver = original; });
    let reveals = 0;
    const cleanup = observeTextOnce({}, () => { reveals += 1; });
    assert.equal(reveals, 1);
    assert.doesNotThrow(cleanup);
});
