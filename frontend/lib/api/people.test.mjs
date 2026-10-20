import assert from 'node:assert/strict';
import test from 'node:test';
import {getPeople, getOwnPublicProfile, savePublicProfile, uploadProfileAvatar, removeProfileAvatar, readOwnProfileAvatar} from './people.ts';
import {personHref, publicAvatarHref, peopleQueryKey} from '../catalog/people.ts';

const publicPerson = {id:41,slug:'anya-test',display_name:'Аня',bio:'Дизайнер',avatar_id:72};
const own = {...publicPerson,is_published:false,version:3};

test('people requests use literal encoded filters, public-only routes and matching SSR key', async t => {
    let call;
    const signal=new AbortController().signal;
    t.mock.method(globalThis,'fetch',async (url,init) => {
        call={url:new URL(url,'https://site.test'),init};
        return Response.json({items:[publicPerson],next_cursor:'next'});
    });
    const result=await getPeople({query:' Аня & мода ',sort:'name',limit:24,cursor:'a+b/c=='},signal);
    assert.equal(call.url.pathname,'/api/people');
    assert.equal(call.url.searchParams.get('query'),'Аня & мода');
    assert.equal(call.url.searchParams.get('cursor'),'a+b/c==');
    assert.equal(call.url.searchParams.get('limit'),'24');
    assert.ok(call.init.signal instanceof AbortSignal);assert.equal(call.init.signal.aborted,false);assert.equal(call.init.cache,'no-store');
    assert.equal(call.init.headers?.Authorization,undefined);
    assert.deepEqual(result,{items:[publicPerson],next_cursor:'next'});
    assert.equal(peopleQueryKey({query:' Аня & мода ',sort:'name',limit:24,cursor:'old'}),'query=%D0%90%D0%BD%D1%8F+%26+%D0%BC%D0%BE%D0%B4%D0%B0&sort=name&limit=24');
    assert.equal(personHref('anya-test'),'/people/anya-test');
    assert.equal(publicAvatarHref(publicPerson),'/api/people/anya-test/avatar/72');
    assert.equal(publicAvatarHref(publicPerson,'card'),'/api/people/anya-test/avatar/72/preview');
    assert.equal(publicAvatarHref({...publicPerson,avatar_id:null}),null);
    assert.equal(publicAvatarHref({...publicPerson,avatar_id:null},'card'),null);
    for(const slug of ['../bad','abc?token=secret','a/b','Aaa','ab','a'.repeat(65)]) assert.throws(()=>personHref(slug),RangeError);
    for(const id of [0,-1,NaN,1.5,2147483648]) assert.throws(()=>publicAvatarHref({...publicPerson,avatar_id:id}),RangeError);
});

test('own profile remains separate and text writes never include IDs, images or private account fields', async t => {
    const calls=[],signal=new AbortController().signal;
    t.mock.method(globalThis,'fetch',async (url,init) => {
        calls.push({url,init});return Response.json(init.method ? own : null);
    });
    assert.equal(await getOwnPublicProfile('session',signal),null);
    assert.deepEqual(await savePublicProfile('session',{...own,email:'private@example.test',user_id:9},signal),own);
    assert.deepEqual(JSON.parse(calls[1].init.body),{slug:'anya-test',display_name:'Аня',bio:'Дизайнер',is_published:false,version:3});
    assert.equal(calls[1].init.method,'PUT');
    for(const {url,init} of calls) {
        assert.equal(url,'/api/profile/public');assert.equal(init.headers.Authorization,'Bearer session');
        assert.equal(init.cache,'no-store');assert.equal(init.signal,signal);
    }
    assert.equal(calls[1].init.headers['Content-Type'],'application/json');
});

test('photo transport uses multipart and binary owner preview, with versions and no token in URL', async t => {
    const calls=[],signal=new AbortController().signal;
    t.mock.method(globalThis,'fetch',async (url,init) => {
        calls.push({url,init});
        return init.method ? Response.json(own) : new Response('photo',{headers:{'Content-Type':'image/webp'}});
    });
    const file=new File(['png'],'portrait.png',{type:'image/png'});
    assert.deepEqual(await uploadProfileAvatar('session',3,file,signal),own);
    assert.equal(calls[0].url,'/api/profile/public/avatar?expected_version=3');
    assert.equal(calls[0].init.method,'POST');assert.ok(calls[0].init.body instanceof FormData);
    assert.equal(calls[0].init.body.get('file').name,'portrait.png');
    assert.equal(await calls[0].init.body.get('file').text(),'png');
    assert.equal(calls[0].init.headers['Content-Type'],undefined);
    assert.deepEqual(await removeProfileAvatar('session',3,signal),own);
    assert.equal(calls[1].init.method,'DELETE');
    const preview=await readOwnProfileAvatar('session',72,signal);
    assert.equal(calls[2].url,'/api/profile/public/avatar/72');
    assert.equal(preview.type,'image/webp');assert.equal(await preview.text(),'photo');
    for(const {url,init} of calls) {
        assert.equal(url.includes('session'),false);assert.equal(init.headers.Authorization,'Bearer session');
        assert.equal(init.signal,signal);assert.equal(init.cache,'no-store');
    }
    await assert.rejects(uploadProfileAvatar('session',0,file),RangeError);
    await assert.rejects(uploadProfileAvatar('session',3,new Blob([new Uint8Array(8*1024*1024+1)],{type:'image/png'})),RangeError);
    await assert.rejects(uploadProfileAvatar('session',3,new Blob(['svg'],{type:'image/svg+xml'})),RangeError);
    await assert.rejects(readOwnProfileAvatar('session',0),RangeError);
    assert.equal(calls.length,3);
});

test('aborted operations and conflict/unavailable responses retain their meaning', async t => {
    const controller=new AbortController();controller.abort();
    let status=409;
    t.mock.method(globalThis,'fetch',async (_url,init) => {
        init.signal?.throwIfAborted();return Response.json({detail:'Unavailable'},{status});
    });
    await assert.rejects(getPeople({},controller.signal),{name:'AbortError'});
    await assert.rejects(savePublicProfile('session',own),error=>error.status===409);
    status=503;await assert.rejects(getOwnPublicProfile('session'),error=>error.status===503);
    status=404;await assert.rejects(readOwnProfileAvatar('session',72),error=>error.status===404);
});
