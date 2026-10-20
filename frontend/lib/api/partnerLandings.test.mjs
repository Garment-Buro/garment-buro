import assert from 'node:assert/strict';
import test from 'node:test';
import {
    readOwnLandingPage,
    getOwnLandings,
    getOwnLanding,
    createOwnLanding,
    updateOwnLanding,
} from './partnerLandings.ts';

test('private landing commands use owner namespace, bounded cursor, no-store and versions without identity', async (t) => {
    const calls = [],
        signal = new AbortController().signal;
    t.mock.method(globalThis, 'fetch', async (url, init) => {
        calls.push({ url, init });
        return Response.json(url.includes('?') ? {items:[{id:7,version:4,slug:'club',title:'Клуб',image_url:null,status:'draft',product_count:2}],next_cursor:null} : {id:7,version:4});
    });
    await getOwnLandings('session', 'a+/=', signal);
    await getOwnLanding('session', 7, signal);
    await createOwnLanding(
        'session',
        {
            slug: 'club',
            title: 'Клуб',
            headline: 'Наша коллекция',
            description: 'Описание',
            cta_label: 'Выбрать',
            cta_href: '/',
            template_key: 'light-running',
            content: { faq: [] },
            product_ids: [22, 11],
            status: 'draft',
            partner_id: 99,
        },
        signal,
    );
    await updateOwnLanding(
        'session',
        7,
        { expected_version: 3, status: 'draft', partner_id: 99, slug: 'changed' },
        signal,
    );
    assert.equal(calls[0].url, '/api/partner/own-landings?limit=24&cursor=a%2B%2F%3D');
    assert.equal(calls[1].url, '/api/partner/own-landings/7');
    assert.equal(calls[2].url, '/api/partner/own-landings');
    assert.equal(calls[2].init.method, 'POST');
    assert.equal(JSON.parse(calls[2].init.body).partner_id, undefined);
    assert.deepEqual(JSON.parse(calls[2].init.body).product_ids, [22, 11]);
    assert.equal(calls[3].init.method, 'PATCH');
    assert.deepEqual(JSON.parse(calls[3].init.body), { expected_version: 3, status: 'draft' });
    for (const { url, init } of calls) {
        assert.equal(init.cache, 'no-store');
        assert.ok(init.signal instanceof AbortSignal);
        assert.equal(init.headers.Authorization, 'Bearer session');
        assert.equal(url.includes('session'), false);
    }
    for (const id of [0, -1, NaN, 1.5])
        assert.throws(() => getOwnLanding('session', id), RangeError);
});

test('owner cards reject old full-list responses and invalid counts without loading a draft', () => {
    const row={id:7,version:4,slug:'club',title:'Клуб',image_url:null,status:'draft',product_count:2};
    assert.deepEqual(readOwnLandingPage({items:[row],next_cursor:null}).items[0],row);
    for(const invalid of [[],{items:[{...row,product_count:undefined}],next_cursor:null},{items:[{...row,product_count:-1}],next_cursor:null},{items:[row,row],next_cursor:null}])assert.throws(()=>readOwnLandingPage(invalid));
});
