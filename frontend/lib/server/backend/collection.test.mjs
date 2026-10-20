import assert from 'node:assert/strict';
import test from 'node:test';
import {createServer} from 'node:http';
import {registerHooks} from 'node:module';

registerHooks({resolve(specifier, context, next) {
    return next(specifier==='server-only'?'next/dist/compiled/server-only/empty.js':specifier, context);
}});

test('collection helper requests only bounded selected IDs and never reads the catalog for an empty list', async t => {
    const {getCollectionProducts} = await import('./collection.ts');
    const calls=[];
    const server=createServer((request,response)=>{
        calls.push({url:request.url,headers:request.headers});
        response.setHeader('Content-Type','application/json');
        response.end(JSON.stringify([{id:8,title:'Модель',price:'3000.50',description:'Точное описание',image_url:null,image_alt:null}]));
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const before=process.env.INTERNAL_API_URL;
    process.env.INTERNAL_API_URL=`http://127.0.0.1:${server.address().port}`;
    t.after(async()=>{
        if(before===undefined)delete process.env.INTERNAL_API_URL;else process.env.INTERNAL_API_URL=before;
        server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
    });
    assert.deepEqual(await getCollectionProducts([]),[]);
    assert.equal(calls.length,0);
    const rows=await getCollectionProducts([8,2,8]);
    assert.equal(rows[0].price,'3000.50');
    assert.equal(rows[0].description,'Точное описание');
    assert.deepEqual(calls.map(call=>call.url),['/api/catalog/collection-products?ids=8&ids=2']);
    assert.equal(calls[0].headers.authorization,undefined);
    assert.equal(calls[0].headers.cookie,undefined);
    await assert.rejects(getCollectionProducts([0]),RangeError);
    await assert.rejects(getCollectionProducts(Array.from({length:51},(_,i)=>i+1)),RangeError);
    assert.equal(calls.length,1);
});

test('model outages and timeout reject rather than fabricate an empty collection', async t => {
    const {getCollectionProducts} = await import('./collection.ts');
    let mode='error';
    const server=createServer((request,response)=>{
        if(mode==='timeout')return;
        response.statusCode=503;response.end('Synthetic failure');
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const before=process.env.INTERNAL_API_URL;
    process.env.INTERNAL_API_URL=`http://127.0.0.1:${server.address().port}`;
    t.after(async()=>{
        if(before===undefined)delete process.env.INTERNAL_API_URL;else process.env.INTERNAL_API_URL=before;
        server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
    });
    await assert.rejects(getCollectionProducts([8]),/status 503/);
    mode='timeout';
    await assert.rejects(getCollectionProducts([8]),{name:'TimeoutError'});
});
