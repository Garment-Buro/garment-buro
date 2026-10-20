import assert from 'node:assert/strict';
import test from 'node:test';
import {createServer} from 'node:http';
import {getConstructorPrice, getConstructorProduct, getStorefrontOptions, getStorefrontProducts} from './storefront.ts';
import {getCommunities} from './communities.ts';
import {getPeople} from './people.ts';
import {PagedResource} from '../catalog/pagedResource.ts';

const flush = async () => {for(let i=0;i<20;i++)await Promise.resolve()};
const stalled = signal => new Promise((_,reject) => {
    signal.throwIfAborted();
    signal.addEventListener('abort',()=>reject(signal.reason),{once:true});
});

test('all public JSON reads end a stalled request after ten seconds, without automatic retries', async t => {
    t.mock.timers.enable({apis:['setTimeout']});
    const controller=new AbortController(),results=[],signals=[];
    t.mock.method(globalThis,'fetch',(_url,init)=>{signals.push(init.signal);return stalled(init.signal)});
    const reads=[signal=>getStorefrontProducts({},signal),getStorefrontOptions,
        signal=>getCommunities({},signal),signal=>getPeople({},signal),
        signal=>getConstructorProduct(42,signal),
        signal=>getConstructorPrice({productId:42,decorations:[]},signal)];
    const pending=reads.map(read=>read(controller.signal).then(()=>results.push('success'),error=>results.push(error.name)));
    try {
        t.mock.timers.tick(9999);await flush();assert.deepEqual(results,[]);
        t.mock.timers.tick(1);await flush();
        assert.deepEqual(results,Array(6).fill('TimeoutError'));
        assert.equal(signals.length,6);assert.ok(signals.every(signal=>signal.aborted));
        assert.equal(controller.signal.aborted,false,'Transport deadline is distinct from owner cancellation');
    } finally {controller.abort();await Promise.all(pending)}
});

test('owner cancellation wins immediately and a finished response releases its deadline', async t => {
    t.mock.timers.enable({apis:['setTimeout']});
    const controller=new AbortController(),reason=new Error('Owner replaced the search');
    let calls=0,completedSignal;
    t.mock.method(globalThis,'fetch',async (_url,init)=>{
        calls++;if(calls===1)return stalled(init.signal);
        completedSignal=init.signal;return Response.json({items:[{id:42}],next_cursor:null});
    });
    const pending=getPeople({},controller.signal);
    controller.abort(reason);await assert.rejects(pending,error=>error===reason);
    await assert.rejects(getPeople({},controller.signal),error=>error===reason);
    assert.equal(calls,1,'Already cancelled work never starts HTTP');
    assert.equal((await getStorefrontProducts({})).items[0].id,42);
    t.mock.timers.tick(10000);await flush();assert.equal(completedSignal.aborted,false);
});

test('public pagination exposes timed-out first reads and retains loaded items/cursor for append retry', async t => {
    t.mock.timers.enable({apis:['setTimeout']});
    let mode='stall';const cursors=[];
    t.mock.method(globalThis,'fetch',async (url,init)=>{
        const cursor=new URL(url,'https://fixture.test').searchParams.get('cursor');cursors.push(cursor);
        return mode==='stall'?stalled(init.signal):Response.json({items:[{id:cursor?43:42}],next_cursor:cursor?null:'next'});
    });
    const resource=new PagedResource();t.after(()=>resource.dispose());
    const first=resource.start('products',(cursor,signal)=>getStorefrontProducts({cursor},signal));
    t.mock.timers.tick(10000);await flush();
    assert.equal(resource.getSnapshot().status,'error');await first;
    mode='ready';await resource.reload();assert.deepEqual(resource.getSnapshot().items,[{id:42}]);
    mode='stall';const more=resource.loadMore();t.mock.timers.tick(10000);await more;
    const state=resource.getSnapshot();assert.equal(state.status,'ready');assert.equal(state.loadingMore,false);
    assert.equal(state.error.name,'TimeoutError');assert.deepEqual(state.items,[{id:42}]);assert.equal(state.nextCursor,'next');
    mode='ready';await resource.loadMore();assert.deepEqual(resource.getSnapshot().items,[{id:42},{id:43}]);
    assert.equal(resource.getSnapshot().error,null);assert.deepEqual(cursors,[null,null,'next','next']);
});

test('native HTTP deadlines cover missing headers and stalled success/error bodies', async t => {
    const requests=[];
    const server=createServer((request,response)=>{
        requests.push(request.url);const query=new URL(request.url,'http://fixture.test').searchParams.get('query');
        if(query==='headers')return;
        response.writeHead(query==='error-body'?503:200,{'Content-Type':'application/json'});response.write('{');
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    t.after(async()=>{server.closeAllConnections();await new Promise(resolve=>server.close(resolve))});
    const fetch=globalThis.fetch,base=`http://127.0.0.1:${server.address().port}`;
    t.mock.method(globalThis,'fetch',(url,init)=>fetch(new URL(url,base),init));
    const controller=new AbortController();t.after(()=>controller.abort());
    // A finite outer guard makes a missing production deadline fail rather than hang CI.
    const guard=setTimeout(()=>controller.abort(new Error('Public read deadline missing')),12000);
    try {
        await Promise.all(['headers','body','error-body'].map(query=>
            assert.rejects(getStorefrontProducts({query},controller.signal),{name:'TimeoutError'})));
        assert.equal(requests.length,3);
    } finally {clearTimeout(guard)}
});
