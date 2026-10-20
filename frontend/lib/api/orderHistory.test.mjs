import assert from 'node:assert/strict';
import test from 'node:test';
import {getAuthOrders, getAuthOrder} from './orderHistory.ts';

test('history uses bounded authenticated metadata pages and one selected detail request', async t => {
    const calls=[],signal=new AbortController().signal;
    t.mock.method(globalThis,'fetch',async (url,init) => {
        calls.push({url,init});
        return Response.json(String(url).includes('/orders?') ? {items:[{id:47}],next_cursor:47} : {id:47,cart_items:'[]'});
    });
    assert.deepEqual(await getAuthOrders('session',null,signal),{items:[{id:47}],next_cursor:47});
    await getAuthOrders('session',47,signal);
    assert.deepEqual(await getAuthOrder('session',47,signal),{id:47,cart_items:'[]'});
    assert.deepEqual(calls.map(call=>call.url),['/api/auth/orders?limit=24','/api/auth/orders?limit=24&cursor=47','/api/orders/47']);
    for(const {url,init} of calls) {
        assert.equal(init.headers.Authorization,'Bearer session');assert.equal(init.cache,'no-store');
        assert.equal(init.signal,signal);assert.equal(url.includes('session'),false);
    }
});

test('invalid cursors/IDs and a mismatched detail cannot expose another order', async t => {
    let calls=0;
    t.mock.method(globalThis,'fetch',async()=>{calls++;return Response.json({id:48});});
    for(const value of [0,-1,1.5,NaN,2147483648]) {
        assert.throws(()=>getAuthOrders('session',value),RangeError);
        await assert.rejects(getAuthOrder('session',value),RangeError);
    }
    assert.equal(calls,0);
    await assert.rejects(getAuthOrder('session',47),error=>error.status===502);
});

test('history preserves cancellation, missing detail and retryable failures', async t => {
    let status=503;
    t.mock.method(globalThis,'fetch',async(_url,init)=>{
        init.signal?.throwIfAborted();return Response.json({detail:'Unavailable'},{status});
    });
    const controller=new AbortController();controller.abort();
    await assert.rejects(getAuthOrders('session',null,controller.signal),{name:'AbortError'});
    await assert.rejects(getAuthOrders('session',47),error=>error.status===503);
    status=404;await assert.rejects(getAuthOrder('session',47),error=>error.status===404);
    status=401;await assert.rejects(getAuthOrder('session',47),error=>error.status===401);
});
