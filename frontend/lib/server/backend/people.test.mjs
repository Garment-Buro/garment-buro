import assert from 'node:assert/strict';
import test from 'node:test';
import {createServer} from 'node:http';
import {registerHooks} from 'node:module';

registerHooks({resolve(specifier,context,next) {
    return next(specifier==='server-only' ? 'next/dist/compiled/server-only/empty.js' : specifier,context);
}});

test('SSR people uses bounded public requests; genuine 404 differs from transient failure', async t => {
    const {getInitialPeople,getPublicPerson}=await import('./people.ts');
    const calls=[];let status=200;
    const person={id:41,slug:'anya-test',display_name:'Аня',bio:'Дизайнер',avatar_id:72};
    const server=createServer((request,response)=>{
        calls.push({url:request.url,headers:request.headers});
        response.statusCode=status;response.setHeader('Content-Type','application/json');
        response.end(JSON.stringify(status===200 ? (request.url.includes('?') ? {items:[person],next_cursor:null} : person) : {detail:'Internal details'}));
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const before=process.env.INTERNAL_API_URL;
    process.env.INTERNAL_API_URL='http://127.0.0.1:'+server.address().port;
    t.after(async()=>{
        if(before===undefined) delete process.env.INTERNAL_API_URL;else process.env.INTERNAL_API_URL=before;
        server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
    });
    assert.deepEqual(await getInitialPeople({limit:4}),{key:'limit=4',page:{items:[person],next_cursor:null}});
    assert.deepEqual(await getPublicPerson('anya-test'),person);
    status=404;assert.equal(await getPublicPerson('anya-test'),null);
    status=503;
    assert.deepEqual(await getInitialPeople({limit:4}),{key:'limit=4',error:'unavailable'});
    await assert.rejects(getPublicPerson('anya-test'));
    await assert.rejects(getPublicPerson('../invalid'),RangeError);
    assert.deepEqual(calls.map(call=>call.url),['/api/people?limit=4','/api/people/anya-test','/api/people/anya-test','/api/people?limit=4','/api/people/anya-test']);
    for(const call of calls) {assert.equal(call.headers.authorization,undefined);assert.equal(call.headers.cookie,undefined)}
});
