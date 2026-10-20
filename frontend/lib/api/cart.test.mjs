import assert from 'node:assert/strict';
import test from 'node:test';
import {createServer} from 'node:http';
import {getCartSnapshot, syncCartSnapshot} from './cart.ts';

test('a failed cart GET remains an error, while an actual empty server cart is data', async t => {
    const calls=[];let status=503;
    t.mock.method(globalThis,'fetch',async(url,options)=>{
        calls.push({url,options});
        return Response.json(status===200?{items:[],updated_at_ms:0}:{detail:'Unavailable'},{status});
    });
    await assert.rejects(getCartSnapshot('fixture/cart'),error=>error.name==='ApiError'&&error.status===503);
    status=200;
    assert.deepEqual(await getCartSnapshot('fixture/cart'),{items:[],updated_at_ms:0});
    for(const call of calls) {
        assert.equal(call.url,'/api/cart/fixture%2Fcart');
        assert.equal(call.options.cache,'no-store');
        assert.equal(call.options.credentials,'same-origin');
    }
});

test('the cart GET deadline covers stalled headers, JSON and HTTP error bodies', async t => {
    let mode='headers';
    const server=createServer((_,response)=>{
        if(mode==='headers')return;
        response.writeHead(mode==='error'?503:200,{'Content-Type':'application/json'});
        response.flushHeaders();response.write('{');
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    t.after(()=>{server.closeAllConnections();return new Promise(resolve=>server.close(resolve))});
    const nativeFetch=globalThis.fetch, nativeTimeout=AbortSignal.timeout.bind(AbortSignal);
    t.mock.method(globalThis,'fetch',(url,options)=>nativeFetch(`http://127.0.0.1:${server.address().port}${url}`,options));
    t.mock.method(AbortSignal,'timeout',milliseconds=>{assert.equal(milliseconds,10_000);return nativeTimeout(100)});
    for(mode of ['headers','json','error'])await assert.rejects(getCartSnapshot('fixture-cart'),{name:'TimeoutError'});
});

test('cart writes keep their explicit snapshot, origin and HTTP error', async t => {
    const update={items:[],expected_revision:null,operation_id:'a'.repeat(32)};let call;
    t.mock.method(globalThis,'fetch',async(url,options)=>{
        call={url,options};return Response.json({detail:'Cart product unavailable'},{status:409});
    });
    await assert.rejects(syncCartSnapshot('fixture-cart',update),error=>error.name==='ApiError'&&error.status===409);
    assert.equal(call.url,'/api/cart/fixture-cart');
    assert.equal(call.options.method,'PUT');assert.equal(call.options.cache,'no-store');
    assert.deepEqual(JSON.parse(call.options.body),update);
});

test('only a version conflict becomes a cart conflict; accepted writes return full server data', async t => {
    const update={items:[],expected_revision:null,operation_id:'a'.repeat(32)};
    let conflict=true;
    t.mock.method(globalThis,'fetch',async()=>conflict
        ? Response.json({detail:{code:'cart_conflict',message:'Changed'}},{status:409})
        : Response.json({items:[],revision:'b'.repeat(32),updated_at_ms:123}));
    await assert.rejects(syncCartSnapshot('fixture-cart',update),{name:'CartRevisionConflictError'});
    conflict=false;
    assert.equal((await syncCartSnapshot('fixture-cart',update)).revision,'b'.repeat(32));
});
