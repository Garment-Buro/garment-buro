import assert from 'node:assert/strict';
import test from 'node:test';

import { AuthSessionCoordinator } from './sessionCoordinator.ts';

const deferred = () => {
    let resolve;
    let reject;
    const promise = new Promise((promiseResolve, promiseReject) => {
        resolve = promiseResolve;
        reject = promiseReject;
    });
    return { promise, reject, resolve };
};

test('concurrent refresh requests share one operation and reset after success', async () => {
    const first = deferred();
    let calls = 0;
    const coordinator = new AuthSessionCoordinator(
        async () => {
            calls += 1;
            return first.promise;
        },
        async () => {},
    );

    const left = coordinator.refresh();
    const right = coordinator.refresh();
    assert.equal(left, right);
    assert.equal(calls, 1);

    const session = { token: 'access-token', user: { id: 1 } };
    first.resolve(session);
    assert.equal(await left, session);
    assert.equal(await right, session);

    await coordinator.refresh();
    assert.equal(calls, 2);
});

test('failed refresh is shared and does not poison later attempts', async () => {
    let calls = 0;
    const coordinator = new AuthSessionCoordinator(
        async () => {
            calls += 1;
            if (calls === 1) throw new Error('offline');
            return { token: 'recovered', user: { id: 1 } };
        },
        async () => {},
    );

    const first = coordinator.refresh();
    const second = coordinator.refresh();
    await assert.rejects(first, /offline/);
    await assert.rejects(second, /offline/);
    assert.equal(calls, 1);
    assert.equal((await coordinator.refresh()).token, 'recovered');
    assert.equal(calls, 2);
});

test('concurrent logout requests share one operation', async () => {
    const pending = deferred();
    let calls = 0;
    const coordinator = new AuthSessionCoordinator(
        async () => ({ token: 'unused', user: { id: 1 } }),
        async () => {
            calls += 1;
            return pending.promise;
        },
    );

    const left = coordinator.logout();
    const right = coordinator.logout();
    assert.equal(left, right);
    assert.equal(calls, 1);
    pending.resolve();
    await Promise.all([left, right]);
});
