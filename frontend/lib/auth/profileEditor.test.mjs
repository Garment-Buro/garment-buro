import assert from 'node:assert/strict';
import test from 'node:test';
import { ProfileEditor } from './profileEditor.ts';

const deferred = () => {
    let resolve;
    const promise = new Promise(ok => { resolve = ok; });
    return { promise, resolve };
};
const user = { id: 1, email: 'customer@example.test', first_name: 'Анна', phone: '' };

test('profile edits reach the server once and publish only the confirmed user', async () => {
    const editor = new ProfileEditor();
    const pending = deferred();
    const writes = [], confirmed = [];
    editor.setAccount('one', user, {
        save: async profile => { writes.push(profile); return pending.promise; },
        remove: async () => {}, confirm: value => confirmed.push(value), logout: async () => {},
    });
    editor.setField('first_name', 'Вера');
    const saving = editor.save();
    await editor.save();
    assert.equal(writes.length, 1);
    assert.equal(writes[0].first_name, 'Вера');
    assert.deepEqual(confirmed, []);
    pending.resolve({ ...user, first_name: 'Вера' });
    assert.equal(await saving, true);
    assert.equal(confirmed[0].first_name, 'Вера');
    assert.equal(editor.getSnapshot().status, 'saved');
});

test('failed profile saves preserve the draft and expose a retryable error', async () => {
    const editor = new ProfileEditor();
    let fail = true;
    editor.setAccount('one', user, {
        save: async profile => { if (fail) throw new TypeError('Offline'); return { ...user, ...profile }; },
        remove: async () => {}, confirm: () => {}, logout: async () => {},
    });
    editor.setField('phone', '+79991234567');
    assert.equal(await editor.save(), false);
    assert.ok(editor.getSnapshot().error);
    assert.equal(editor.getSnapshot().profile.phone, '+79991234567');
    fail = false;
    assert.equal(await editor.save(), true);
    assert.equal(editor.getSnapshot().error, null);
});

test('switching accounts cancels the old save and cannot overwrite the new account', async () => {
    const editor = new ProfileEditor();
    const pending = deferred();
    let signal;
    editor.setAccount('one', user, {
        save: async (_, value) => { signal = value; return pending.promise; },
        remove: async () => {}, confirm: () => assert.fail('old user published'), logout: async () => {},
    });
    const saving = editor.save();
    editor.setAccount('two', { ...user, id: 2, first_name: 'Борис' }, {
        save: async () => {}, remove: async () => {}, confirm: () => {}, logout: async () => {},
    });
    assert.equal(signal.aborted, true);
    pending.resolve({ ...user, first_name: 'Old response' });
    assert.equal(await saving, false);
    assert.equal(editor.getSnapshot().profile.first_name, 'Борис');
});

test('account deletion logs out only after backend confirmation and retains errors on refusal', async () => {
    const editor = new ProfileEditor();
    let fail = true, logouts = 0;
    editor.setAccount('one', user, {
        save: async () => user,
        remove: async () => { if (fail) throw new Error('Unavailable'); },
        confirm: () => {}, logout: async () => { logouts++; },
    });
    assert.equal(await editor.remove(), false);
    assert.equal(logouts, 0);
    assert.ok(editor.getSnapshot().error);
    fail = false;
    assert.equal(await editor.remove(), true);
    assert.equal(logouts, 1);
});
