import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError } from '../api/http.ts';
import { LandingEditor, landingDirty, landingCard } from './landingEditor.ts';

const own = {
    id: 7,
    partner_id: 2,
    version: 3,
    slug: 'our-club',
    title: 'Клуб',
    eyebrow: null,
    headline: 'Наша коллекция',
    description: 'История',
    cta_label: 'Выбрать',
    cta_href: '/',
    image_url: null,
    template_key: 'light-running',
    content: { faq: [] },
    product_ids: [22, 11],
    status: 'draft',
    published_at: null,
    created_at: '2026-10-16T00:00:00Z',
    updated_at: '2026-10-16T00:00:00Z',
};
const deferred = () => {
    let resolve;
    const promise = new Promise((ok) => {
        resolve = ok;
    });
    return { promise, resolve };
};
const transport = (overrides = {}) => ({
    list: async () => ({ items: [landingCard(own)], next_cursor: null }),
    load: async () => own,
    create: async (value) => ({ ...own, ...value, version: 1 }),
    update: async (id, value) => ({ ...own, ...value, id, version: value.expected_version + 1 }),
    ...overrides,
});

test('a new collection is saved privately; publication requires saved nonempty products', async () => {
    const editor = new LandingEditor(),
        writes = [];
    await editor.setAccount(
        'one',
        transport({
            create: async (value) => {
                writes.push(value);
                return { ...own, ...value, version: 1 };
            },
            update: async (id, value) => {
                writes.push(value);
                return { ...own, id, version: 2, status: value.status };
            },
        }),
    );
    editor.createDraft();
    editor.setField('slug', 'new-club');
    editor.setField('title', 'Новый клуб');
    assert.equal(await editor.publish(true), false);
    editor.setProducts([11, 22]);
    assert.equal(await editor.save(), true);
    assert.equal(writes[0].status, 'draft');
    assert.deepEqual(writes[0].product_ids, [11, 22]);
    assert.equal(writes[0].partner_id, undefined);
    assert.equal(editor.getSnapshot().record.version, 1);
    editor.setField('description', 'Не готово');
    assert.equal(await editor.publish(true), false);
    await editor.reload();
    assert.equal(await editor.publish(true), true);
    assert.deepEqual(writes[1], { expected_version: 3, status: 'published' });
    editor.dispose();
});

test('unpublishing sends status only and preserves unsaved text and unavailable selected IDs', async () => {
    const editor = new LandingEditor(),
        writes = [];
    await editor.setAccount(
        'one',
        transport({
            load: async () => ({ ...own, status: 'published' }),
            update: async (id, value) => {
                writes.push(value);
                return { ...own, id, status: value.status, version: 4 };
            },
        }),
    );
    await editor.open(7);
    editor.setField('headline', 'Позже');
    editor.setProducts([999, 11]);
    assert.equal(await editor.publish(false), true);
    assert.deepEqual(writes, [{ expected_version: 3, status: 'draft' }]);
    assert.equal(editor.getSnapshot().draft.headline, 'Позже');
    assert.deepEqual(editor.getSnapshot().draft.product_ids, [999, 11]);
    assert.equal(landingDirty(editor.getSnapshot()), true);
    await editor.save();
    assert.equal(writes[1].expected_version, 4);
    assert.equal(writes[1].slug, undefined);
    assert.equal(writes[1].status, undefined);
    editor.dispose();
});

test('a version conflict retains the draft and blocks another write until explicit reload', async () => {
    const editor = new LandingEditor();
    let calls = 0;
    await editor.setAccount(
        'one',
        transport({
            update: async () => {
                calls++;
                throw new ApiError('Conflict', 409);
            },
        }),
    );
    await editor.open(7);
    editor.setField('title', 'Мои правки');
    assert.equal(await editor.save(), false);
    assert.equal(editor.getSnapshot().conflict, true);
    assert.equal(editor.getSnapshot().draft.title, 'Мои правки');
    assert.equal(await editor.save(), false);
    assert.equal(await editor.publish(false), false);
    assert.equal(calls, 1);
    await editor.reload();
    assert.equal(editor.getSnapshot().conflict, false);
    assert.equal(editor.getSnapshot().draft.title, 'Клуб');
    editor.dispose();
});

test('failed saves retain input; retry is single flight and confirms the returned version', async () => {
    const editor = new LandingEditor(),
        pending = deferred();
    let calls = 0;
    await editor.setAccount(
        'one',
        transport({
            update: async (id, value) => {
                calls++;
                if (calls === 1) throw new TypeError('Offline');
                await pending.promise;
                return { ...own, id, ...value, version: 4 };
            },
        }),
    );
    await editor.open(7);
    editor.setField('title', 'Мои правки');
    assert.equal(await editor.save(), false);
    const retry = editor.save();
    assert.equal(await editor.save(), false);
    pending.resolve();
    assert.equal(await retry, true);
    assert.equal(calls, 2);
    assert.equal(editor.getSnapshot().record.version, 4);
    assert.equal(landingDirty(editor.getSnapshot()), false);
    editor.dispose();
});

test('account replacement aborts old reads and suppresses late successful commands', async () => {
    const editor = new LandingEditor(),
        late = deferred(),
        write = deferred();
    let signal;
    const loading = editor.setAccount(
        'old',
        transport({
            list: async (_, s) => {
                signal = s;
                return late.promise;
            },
        }),
    );
    await editor.setAccount(
        'new',
        transport({ list: async () => ({ items: [], next_cursor: null }) }),
    );
    assert.equal(signal.aborted, true);
    late.resolve({ items: [landingCard(own)], next_cursor: null });
    await loading;
    assert.deepEqual(editor.getSnapshot().items, []);
    await editor.setAccount(
        'old',
        transport({
            update: async (_, __, s) => {
                signal = s;
                return write.promise;
            },
        }),
    );
    await editor.open(7);
    editor.setField('title', 'Старое');
    const saving = editor.save();
    await editor.setAccount(
        'new',
        transport({ list: async () => ({ items: [], next_cursor: null }) }),
    );
    assert.equal(signal.aborted, true);
    write.resolve({ ...own, version: 4 });
    assert.equal(await saving, false);
    assert.equal(editor.getSnapshot().record, null);
    assert.equal(editor.getSnapshot().editing, false);
    assert.deepEqual(editor.getSnapshot().items, []);
    editor.dispose();
});

test('bounded list pages append unique entries and selected products remain ordered and limited', async () => {
    const editor = new LandingEditor(),
        cursors = [];
    await editor.setAccount(
        'one',
        transport({
            list: async (cursor) => {
                cursors.push(cursor);
                return cursor
                    ? { items: [landingCard(own), { ...landingCard(own), id: 6 }], next_cursor: null }
                    : { items: [landingCard(own)], next_cursor: 'next' };
            },
        }),
    );
    await editor.more();
    assert.deepEqual(cursors, [null, 'next']);
    assert.deepEqual(
        editor.getSnapshot().items.map((x) => x.id),
        [7, 6],
    );
    editor.createDraft();
    editor.setProducts([22, 11, 22]);
    assert.deepEqual(editor.getSnapshot().draft.product_ids, [22, 11]);
    editor.setProducts(Array.from({ length: 51 }, (_, i) => i + 1));
    assert.equal(editor.getSnapshot().draft.product_ids.length, 2);
    editor.dispose();
});

test('a busy new slug can be corrected without discarding the new collection draft', async () => {
    const editor = new LandingEditor();
    let calls = 0;
    await editor.setAccount(
        'one',
        transport({
            create: async (value) => {
                calls++;
                if (calls === 1) throw new ApiError('Slug taken', 409);
                return { ...own, ...value, version: 1 };
            },
        }),
    );
    editor.createDraft();
    editor.setField('slug', 'occupied');
    editor.setField('title', 'Мой клуб');
    await editor.save();
    assert.equal(editor.getSnapshot().conflict, true);
    editor.setField('slug', 'new-available');
    assert.equal(await editor.save(), true);
    assert.equal(editor.getSnapshot().record.slug, 'new-available');
    assert.equal(editor.getSnapshot().record.title, 'Мой клуб');
    editor.dispose();
});

test('a confirmed full detail replaces only its compact list card', async () => {
    const editor = new LandingEditor();
    await editor.setAccount('one',transport());
    assert.equal(editor.getSnapshot().record,null);
    assert.equal(editor.getSnapshot().items[0].product_count,2);
    assert.equal('content' in editor.getSnapshot().items[0],false);
    await editor.open(7);editor.setProducts([11]);await editor.save();
    assert.equal(editor.getSnapshot().record.product_ids.length,1);
    assert.equal(editor.getSnapshot().items[0].product_count,1);
    assert.equal('product_ids' in editor.getSnapshot().items[0],false);
    editor.dispose();
});
