import assert from 'node:assert/strict';
import test from 'node:test';
import { FavoriteController } from './favoriteController.ts';

const deferred = () => {
    let resolve, reject;
    const promise = new Promise((ok, fail) => {resolve=ok; reject=fail});
    return {promise, resolve, reject};
};

test('an account change clears all statuses and prevents the old request from publishing', async () => {
    const controller = new FavoriteController();
    const old = deferred();
    let signal;
    controller.setAccount('one', {status:(_, value) => {signal=value; return old.promise}, save:async () => {}});
    const pending = controller.ensureStatus([1,2]);
    controller.setAccount('two', {status:async () => [2], save:async () => {}});
    assert.equal(signal.aborted, true);
    assert.deepEqual(controller.getSnapshot().ids, []);
    await controller.ensureStatus([1,2]);
    old.resolve([1]);
    await pending;
    assert.deepEqual(controller.getSnapshot().ids, [2]);
    assert.equal(controller.getSnapshot().account, 'two');
});

test('a favorite is changed only after a successful backend write; repeated clicks are serialized', async () => {
    const controller = new FavoriteController();
    const pending = deferred();
    const saves = [];
    controller.setAccount('one', {status:async () => [], save:(id, wanted) => {saves.push([id,wanted]); return pending.promise}});
    await controller.ensureStatus([42]);
    const saving = controller.toggle(42);
    assert.deepEqual(controller.getSnapshot().ids, []);
    assert.deepEqual(controller.getSnapshot().pendingIds, [42]);
    assert.equal(await controller.toggle(42), false);
    assert.deepEqual(saves, [[42,true]]);
    pending.resolve();
    assert.equal(await saving, true);
    assert.deepEqual(controller.getSnapshot().ids, [42]);
    assert.deepEqual(controller.getSnapshot().pendingIds, []);
});

test('failed writes preserve the confirmed favorite state and can be retried', async () => {
    const controller = new FavoriteController();
    let fail = true;
    controller.setAccount('one', {status:async () => [42], save:async () => {if(fail) throw new Error('Offline')}});
    await controller.ensureStatus([42]);
    assert.equal(await controller.toggle(42), false);
    assert.deepEqual(controller.getSnapshot().ids, [42]);
    assert.ok(controller.getSnapshot().error);
    fail = false;
    assert.equal(await controller.toggle(42), true);
    assert.deepEqual(controller.getSnapshot().ids, []);
});

test('unconfirmed cards cannot overwrite an existing favorite and membership batches stay bounded', async () => {
    const controller = new FavoriteController();
    const calls = [];
    controller.setAccount('one', {status:async ids => {calls.push(ids); return [ids[0]]}, save:async () => {assert.fail('unconfirmed write')}});
    assert.equal(await controller.toggle(42), false);
    await controller.ensureStatus(Array.from({length:205}, (_, index) => index+1));
    assert.deepEqual(calls.map(ids => ids.length), [100,100,5]);
    await controller.ensureStatus([1,2,3]);
    assert.equal(calls.length, 3);
});

test('retry refreshes a previously known status after a failed save without interrupting a pending save', async () => {
    const controller = new FavoriteController();
    const saving = deferred();
    let reads = 0;
    controller.setAccount('one', {status:async () => {reads++; return reads === 1 ? [42] : []}, save:async id => {
        if(id === 42) throw new Error('Lost response');
        return saving.promise;
    }});
    await controller.ensureStatus([42,43]);
    await controller.toggle(42);
    assert.ok(controller.getSnapshot().error);
    const pending = controller.toggle(43);
    await controller.refreshStatus([42,43]);
    assert.equal(reads, 2);
    assert.deepEqual(controller.getSnapshot().ids, []);
    assert.deepEqual(controller.getSnapshot().pendingIds, [43]);
    saving.resolve();
    assert.equal(await pending, true);
    assert.deepEqual(controller.getSnapshot().ids, [43]);
});

test('overlapping membership loads do not re-read batches already claimed by another load', async () => {
    const controller = new FavoriteController();
    const first = deferred(), second = deferred();
    const calls = [];
    controller.setAccount('one', {status:ids => {
        calls.push(ids);
        if(ids[0] === 1) return first.promise;
        if(ids[0] === 101) return second.promise;
        return Promise.resolve([]);
    }, save:async () => {}});
    const ids = Array.from({length:205}, (_,i)=>i+1);
    const original = controller.ensureStatus(ids);
    const overlapping = controller.ensureStatus(ids);
    first.resolve([]);
    await Promise.resolve();
    await Promise.resolve();
    assert.deepEqual(calls.map(batch=>batch[0]), [1,101,201]);
    second.resolve([]);
    await Promise.all([original,overlapping]);
    assert.equal(calls.length,3);
    assert.equal(controller.getSnapshot().knownIds.length,205);
});
