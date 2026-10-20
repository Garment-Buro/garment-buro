import assert from 'node:assert/strict';
import test from 'node:test';
import {createServer} from 'node:http';
import {registerHooks} from 'node:module';

// Node tests execute the server code outside Next's RSC resolver.
registerHooks({resolve(specifier, context, next) {
    if(specifier === 'server-only') return next('next/dist/compiled/server-only/empty.js', context);
    return next(specifier, context);
}});

test('server first page uses the public backend query and stays fresh without account headers', async t => {
    const {getInitialStorefront} = await import('./storefront.ts');
    const calls=[];
    let price='3000.50';
    const server=createServer((request,response)=>{
        calls.push({url:request.url,headers:request.headers});
        response.setHeader('Content-Type','application/json');
        response.end(JSON.stringify({items:[{id:42,title:'Худи',price,category_id:3,category_name:'Одежда',colors:['Чёрный'],tags:[],source:'garment_buro',image_url:'https://media.example/42.webp',image_alt:null}],next_cursor:'next'}));
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const before=process.env.INTERNAL_API_URL;
    process.env.INTERNAL_API_URL=`http://127.0.0.1:${server.address().port}`;
    t.after(async()=>{
        if(before===undefined)delete process.env.INTERNAL_API_URL;else process.env.INTERNAL_API_URL=before;
        server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
    });
    const first=await getInitialStorefront({minPrice:0,sort:'newest',limit:24});
    assert.equal(first.key,'min_price=0&sort=newest&limit=24');
    assert.equal(first.page.items[0].price,'3000.50');
    assert.equal(first.page.next_cursor,'next');
    price='3500.00';
    const second=await getInitialStorefront({limit:24,sort:'newest',minPrice:0});
    assert.equal(second.key,first.key);
    assert.equal(second.page.items[0].price,'3500.00');
    assert.deepEqual(calls.map(call=>call.url),['/api/catalog/products?min_price=0&sort=newest&limit=24','/api/catalog/products?min_price=0&sort=newest&limit=24']);
    for(const call of calls){assert.equal(call.headers.authorization,undefined);assert.equal(call.headers.cookie,undefined)}
});

test('backend failure or invalid JSON yields a safe retryable error instead of demo or raw upstream data', async t => {
    const {getInitialStorefront} = await import('./storefront.ts');
    let status=503;
    const server=createServer((request,response)=>{response.statusCode=status;response.end('private upstream diagnostics')});
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const before=process.env.INTERNAL_API_URL;
    process.env.INTERNAL_API_URL=`http://127.0.0.1:${server.address().port}`;
    t.after(async()=>{
        if(before===undefined)delete process.env.INTERNAL_API_URL;else process.env.INTERNAL_API_URL=before;
        server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
    });
    assert.deepEqual(await getInitialStorefront({limit:4}),{key:'limit=4',error:'unavailable'});
    status=200;
    assert.deepEqual(await getInitialStorefront({limit:4}),{key:'limit=4',error:'unavailable'});
});

test('a stalled backend is aborted so initial storefront rendering can finish with retry', async t => {
    const {getInitialStorefront} = await import('./storefront.ts');
    const server=createServer(()=>{});
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const before=process.env.INTERNAL_API_URL;
    process.env.INTERNAL_API_URL=`http://127.0.0.1:${server.address().port}`;
    t.after(async()=>{
        if(before===undefined)delete process.env.INTERNAL_API_URL;else process.env.INTERNAL_API_URL=before;
        server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
    });
    assert.deepEqual(await getInitialStorefront({limit:4}),{key:'limit=4',error:'unavailable'});
});
