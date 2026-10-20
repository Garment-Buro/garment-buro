import test from 'node:test';
import assert from 'node:assert/strict';
import { createPointerSession } from './pointerSession.ts';

class TrackedTarget extends EventTarget {
    listeners = new Map();
    addEventListener(type, callback) {
        super.addEventListener(type, callback);
        if (!this.listeners.has(type)) this.listeners.set(type, new Set());
        this.listeners.get(type).add(callback);
    }
    removeEventListener(type, callback) {
        super.removeEventListener(type, callback);
        this.listeners.get(type)?.delete(callback);
    }
    count() { return [...this.listeners.values()].reduce((count, values) => count + values.size, 0); }
}
const pointer = (type, pointerId) => Object.assign(new Event(type), { pointerId });
const fixture = () => {
    const target = new TrackedTarget();
    const visibility = Object.assign(new TrackedTarget(), { hidden: false });
    const session = createPointerSession(target, visibility);
    const calls = [];
    const handlers = { onMove: event => calls.push(['move', event.pointerId]), onEnd: event => calls.push(['end', event.pointerId]), onCancel: () => calls.push(['cancel']) };
    return { target, visibility, session, calls, handlers };
};

test('one pointer moves and completes; other fingers cannot move or end it', () => {
    const { target, visibility, session, calls, handlers } = fixture();
    session.start(7, handlers);
    for (const type of ['pointermove', 'pointerup', 'pointercancel']) target.dispatchEvent(pointer(type, 9));
    assert.deepEqual(calls, []);
    target.dispatchEvent(pointer('pointermove', 7));
    target.dispatchEvent(pointer('pointerup', 7));
    target.dispatchEvent(pointer('pointermove', 7));
    assert.deepEqual(calls, [['move', 7], ['end', 7]]);
    assert.equal(target.count() + visibility.count(), 0);
});

test('pointer cancellation never confirms a deferred selection', () => {
    const { target, visibility, session, calls, handlers } = fixture();
    session.start(7, handlers);
    target.dispatchEvent(pointer('pointercancel', 7));
    target.dispatchEvent(pointer('pointerup', 7));
    assert.deepEqual(calls, [['cancel']]);
    assert.equal(target.count() + visibility.count(), 0);
});

test('a new gesture revokes the old one, including queued callbacks', () => {
    const { target, visibility, session, calls, handlers } = fixture();
    session.start(7, handlers);
    const oldMove = [...target.listeners.get('pointermove')][0];
    const oldEnd = [...target.listeners.get('pointerup')][0];
    session.start(9, handlers);
    oldMove(pointer('pointermove', 7));
    oldEnd(pointer('pointerup', 7));
    target.dispatchEvent(pointer('pointermove', 9));
    target.dispatchEvent(pointer('pointerup', 9));
    assert.deepEqual(calls, [['cancel'], ['move', 9], ['end', 9]]);
    assert.equal(target.count() + visibility.count(), 0);
});

test('editor disposal clears listeners and blocks stale starts or completions', () => {
    const { target, visibility, session, calls, handlers } = fixture();
    session.start(7, handlers);
    const oldEnd = [...target.listeners.get('pointerup')][0];
    session.dispose();
    session.dispose();
    session.start(9, handlers);
    oldEnd(pointer('pointerup', 7));
    assert.deepEqual(calls, [['cancel']]);
    assert.equal(target.count() + visibility.count(), 0);
});

for (const reason of ['blur', 'hidden', 'explicit cancel']) {
    test(`${reason} ends the gesture without a click or trailing listener`, () => {
        const { target, visibility, session, calls, handlers } = fixture();
        session.start(7, handlers);
        visibility.dispatchEvent(new Event('visibilitychange'));
        assert.deepEqual(calls, []);
        if (reason === 'blur') target.dispatchEvent(new Event('blur'));
        else if (reason === 'hidden') {
            visibility.hidden = true;
            visibility.dispatchEvent(new Event('visibilitychange'));
        } else session.cancel();
        target.dispatchEvent(pointer('pointerup', 7));
        assert.deepEqual(calls, [['cancel']]);
        assert.equal(target.count() + visibility.count(), 0);
    });
}

test('starting in an already hidden document cannot leave an active gesture', () => {
    const { target, visibility, session, calls, handlers } = fixture();
    visibility.hidden = true;
    session.start(7, handlers);
    assert.deepEqual(calls, [['cancel']]);
    assert.equal(target.count() + visibility.count(), 0);
});
