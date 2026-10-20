import assert from 'node:assert/strict';
import test from 'node:test';
import {getCommunities, getCommunityFavoriteStatus, getSavedCommunities, setCommunityFavorite} from './communities.ts';
import {communityHref, communityQueryKey} from '../catalog/communities.ts';

test('community directory sends encoded search, sort and opaque cursor to the same-origin backend', async t => {
    let call;
    const signal = new AbortController().signal;
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        call = {url:new URL(url, 'https://site.test'), init};
        return Response.json({items:[{id:42, title:'Беговой клуб', slug:'running'}], next_cursor:'next'});
    });
    const page = await getCommunities({query:' Бег & лето ', sort:'name', limit:24, cursor:'a+b/c=='}, signal);
    assert.equal(call.url.pathname, '/api/communities');
    assert.equal(call.url.searchParams.get('query'), 'Бег & лето');
    assert.equal(call.url.searchParams.get('sort'), 'name');
    assert.equal(call.url.searchParams.get('limit'), '24');
    assert.equal(call.url.searchParams.get('cursor'), 'a+b/c==');
    assert.ok(call.init.signal instanceof AbortSignal); assert.equal(call.init.signal.aborted, false); assert.equal(call.init.cache, 'no-store');
    assert.equal(call.init.headers?.Authorization, undefined);
    assert.equal(page.items[0].id, 42); assert.equal(page.next_cursor, 'next');
    assert.equal(communityQueryKey({query:' Бег & лето ', sort:'name', limit:24, cursor:'old'}), 'query=%D0%91%D0%B5%D0%B3+%26+%D0%BB%D0%B5%D1%82%D0%BE&sort=name&limit=24');
    assert.equal(communityHref('running'), '/p/running');
    assert.throws(() => communityHref('../wrong'), RangeError);
});

test('community favorites persist through account requests, with bounded IDs and idempotent HTTP verbs', async t => {
    const calls = [], signal = new AbortController().signal;
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        calls.push({url:new URL(url, 'https://site.test'), init});
        return init.method ? new Response(null,{status:204}) : Response.json({community_ids:[42], items:[{id:42}], next_cursor:7});
    });
    assert.deepEqual(await getCommunityFavoriteStatus([], 'session', signal), []);
    assert.equal(calls.length, 0);
    assert.deepEqual(await getCommunityFavoriteStatus([42,43,42], 'session', signal), [42]);
    assert.deepEqual(calls[0].url.searchParams.getAll('community_ids'), ['42','43']);
    await setCommunityFavorite(42, true, 'session', signal);
    await setCommunityFavorite(42, false, 'session', signal);
    const page = await getSavedCommunities('session', {limit:24, cursor:51}, signal);
    assert.deepEqual(calls.map(call => call.url.pathname), ['/api/profile/community-favorites/status','/api/profile/community-favorites/42','/api/profile/community-favorites/42','/api/profile/community-favorites']);
    assert.deepEqual(calls.slice(1,3).map(call => call.init.method), ['PUT','DELETE']);
    assert.equal(calls[3].url.searchParams.get('cursor'), '51'); assert.equal(page.items[0].id, 42);
    for (const {init} of calls) {
        assert.equal(init.headers.Authorization, 'Bearer session'); assert.equal(init.cache, 'no-store'); assert.equal(init.signal, signal);
    }
    await assert.rejects(getCommunityFavoriteStatus(Array.from({length:101},(_,i)=>i+1), 'session'), RangeError);
    await assert.rejects(setCommunityFavorite(0,true,'session'), RangeError);
    assert.equal(calls.length,4);
});

test('cancelled reads and rejected community writes reach the caller without invented success', async t => {
    const controller = new AbortController(); controller.abort();
    t.mock.method(globalThis, 'fetch', async (_url,init) => {
        init.signal?.throwIfAborted(); return Response.json({detail:'Unavailable'},{status:404});
    });
    await assert.rejects(getCommunities({},controller.signal), {name:'AbortError'});
    await assert.rejects(setCommunityFavorite(42,true,'session'), error => error.status === 404);
});
