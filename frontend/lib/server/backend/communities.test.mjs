import assert from 'node:assert/strict';
import test from 'node:test';
import {createServer} from 'node:http';
import {registerHooks} from 'node:module';

registerHooks({resolve(specifier,context,next) {
    return next(specifier === 'server-only' ? 'next/dist/compiled/server-only/empty.js' : specifier,context);
}});

test('initial communities are public, fresh and retryable when backend data is unavailable', async t => {
    const {getInitialCommunities} = await import('./communities.ts');
    const calls = []; let status = 200;
    const server = createServer((request,response) => {
        calls.push({url:request.url,headers:request.headers});
        response.statusCode=status; response.setHeader('Content-Type','application/json');
        response.end(JSON.stringify(status===200 ? {items:[{id:42,title:'Коллекция',slug:'running'}],next_cursor:null} : {detail:'Private diagnostics'}));
    });
    await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
    const before = process.env.INTERNAL_API_URL;
    process.env.INTERNAL_API_URL = 'http://127.0.0.1:' + server.address().port;
    t.after(async () => {
        if(before === undefined) delete process.env.INTERNAL_API_URL; else process.env.INTERNAL_API_URL=before;
        server.closeAllConnections(); await new Promise(resolve => server.close(resolve));
    });
    const first = await getInitialCommunities({limit:4});
    assert.equal(first.key,'limit=4'); assert.equal(first.page.items[0].id,42);
    status=503;
    assert.deepEqual(await getInitialCommunities({limit:4}),{key:'limit=4',error:'unavailable'});
    assert.deepEqual(calls.map(call => call.url),['/api/communities?limit=4','/api/communities?limit=4']);
    for(const call of calls) {assert.equal(call.headers.authorization,undefined);assert.equal(call.headers.cookie,undefined)}
});
