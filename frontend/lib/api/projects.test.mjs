import assert from 'node:assert/strict';
import test from 'node:test';
import {
    createProject,
    updateProject,
    deleteProject,
    getProject,
    getProjects,
    getProjectByClientKey,
    getProjectImages,
    uploadProjectImage,
} from './projects.ts';

test('project CRUD and image batches use authenticated same-origin requests without browser persistence', async (t) => {
    const calls = [];
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        calls.push({ url: new URL(url, 'https://site.test'), init });
        return init.method === 'DELETE'
            ? new Response(null, { status: 204 })
            : Response.json({ id: 42 });
    });
    const payload = {
        client_key: 'stable-key',
        product_id: 17,
        kind: 'draft',
        title: 'Мой проект',
        snapshot: { schemaVersion: 1 },
    };
    const signal = new AbortController().signal;
    await createProject(payload, 'session', signal);
    await updateProject(
        42,
        { expected_version: 3, kind: 'draft', title: 'Название', snapshot: {} },
        'session',
        signal,
    );
    await getProject(42, 'session', signal);
    await getProjects('collection', 'session', { limit: 24, cursor: 51 }, signal);
    await getProjectImages(42, 3, 'session', signal);
    await uploadProjectImage(new Blob(['png-bytes'], { type: 'image/png' }), 'session', signal);
    await deleteProject(42, 3, 'session', signal);
    assert.deepEqual(
        calls.map((call) => call.url.pathname),
        [
            '/api/profile/projects',
            '/api/profile/projects/42',
            '/api/profile/projects/42',
            '/api/profile/projects',
            '/api/profile/projects/42/media',
            '/api/profile/project-media',
            '/api/profile/projects/42',
        ],
    );
    for (const { init } of calls) {
        assert.equal(init.headers.Authorization, 'Bearer session');
        assert.equal(init.cache, 'no-store');
        assert.equal(init.signal, signal);
    }
    assert.equal(calls[3].url.searchParams.get('kind'), 'collection');
    assert.equal(calls[3].url.searchParams.get('cursor'), '51');
    assert.equal(calls[4].url.searchParams.get('version'), '3');
    assert.equal(calls[6].url.searchParams.get('expected_version'), '3');
    assert.equal(JSON.parse(calls[0].init.body).client_key, 'stable-key');
    assert.ok(calls[5].init.body instanceof FormData);
    assert.equal(calls[5].init.headers['Content-Type'], undefined);
});

test('version conflicts, upload failure and abort reach the caller', async (t) => {
    t.mock.method(globalThis, 'fetch', async (_, init) => {
        init.signal?.throwIfAborted();
        return Response.json({ detail: 'Conflict' }, { status: 409 });
    });
    await assert.rejects(
        updateProject(42, { expected_version: 1 }, 'session'),
        (error) => error.status === 409,
    );
    await assert.rejects(
        uploadProjectImage(new Blob(['png']), 'session'),
        (error) => error.status === 409,
    );
    const controller = new AbortController();
    controller.abort();
    await assert.rejects(getProject(42, 'session', controller.signal), { name: 'AbortError' });
    assert.throws(() => getProject(-1, 'session'), RangeError);
    assert.throws(() => getProjectImages(42, 0, 'session'), RangeError);
});

test('migration receipts are authenticated, uncached and distinguish missing from deleted', async t => {
    const calls = [];
    let status = 200;
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        calls.push({ url, init });
        return Response.json(status === 200 ? { id: 42, version: 2 } : { detail: 'Unavailable' }, { status });
    });
    const signal = new AbortController().signal;
    assert.equal((await getProjectByClientKey('legacy-v1-key', 'session', signal)).id, 42);
    assert.equal(calls[0].url, '/api/profile/projects/by-client-key/legacy-v1-key');
    assert.equal(calls[0].init.headers.Authorization, 'Bearer session');
    assert.equal(calls[0].init.cache, 'no-store'); assert.equal(calls[0].init.signal, signal);
    status = 404; assert.equal(await getProjectByClientKey('missing', 'session'), null);
    status = 410; await assert.rejects(getProjectByClientKey('deleted', 'session'), error => error.status === 410);
    status = 503; await assert.rejects(getProjectByClientKey('uncertain', 'session'), error => error.status === 503);
    assert.throws(() => getProjectByClientKey('../bad', 'session'), RangeError);
});
