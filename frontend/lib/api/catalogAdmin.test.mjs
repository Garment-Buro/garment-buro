import assert from 'node:assert/strict';
import test from 'node:test';
import {requestCatalogAdminPage} from './catalogAdmin.ts';
import {readCatalogAdminPage} from '../products/adminCatalog.ts';
import {PageCursorExpiredError, PagedResource} from '../catalog/pagedResource.ts';

const product = (id=42) => ({id,title:'Модель',slug:null,category_id:null,garment_model_id:null,
    category_name:null,garment_model_name:null,preset_source:'garment_buro',tags:[],price:'80.00',old_price:null,
    image_url:null,is_active:true,stock_quantity:3,variant_count:5,sku:'SKU',community_count:0,communities:[]});
const page = (id=42,cursor=null) => ({items:[product(id)],next_cursor:cursor});

test('administrative reads send bounded server filters, bearer or cookie session and no-store', async t => {
    const calls=[];
    t.mock.method(globalThis,'fetch',async (url,init) => {calls.push({url,init});return Response.json(page())});
    const signal=new AbortController().signal;
    for(const path of ['/products','/production/admin/assortment/products']) {
        const result=await requestCatalogAdminPage(path,{query:'_%\\ & Ж',active:false,stock:'available',source:'user',
            community_id:9,sort:'stock:desc',limit:24,cursor:'opaque+='},
            {signal,...(path==='/products'?{headers:{Authorization:'Bearer test-token'}}:{})});
        assert.equal(result.items[0].id,42);
    }
    for(const call of calls) {
        const query=new URL(call.url,'https://test.invalid').searchParams;
        assert.equal(query.get('query'),'_%\\ & Ж');assert.equal(query.get('active'),'false');
        assert.equal(query.get('limit'),'24');assert.equal(query.get('cursor'),'opaque+=');
        assert.equal(query.get('community_id'),'9');assert.equal(query.get('sort'),'stock:desc');
        assert.equal(call.init.cache,'no-store');assert.equal(call.init.credentials,'same-origin');
    }
    assert.equal(new Headers(calls[0].init.headers).get('Authorization'),'Bearer test-token');
    assert.equal(new Headers(calls[1].init.headers).has('Authorization'),false);
});

test('malformed pages, duplicate identities and malformed compact references fail visibly', () => {
    for(const malformed of [[],{items:[],next_cursor:''},page(42,12),{items:[product(),product()],next_cursor:null},
        {items:Array.from({length:101},(_,i)=>product(i+1)),next_cursor:null},
        ...[{price:''},{price:'NaN'},{price:'-1'},{variant_count:-1},{category_id:-1},
            {community_count:2,communities:[{id:1,title:'a',slug:'a'},{id:1,title:'b',slug:'b'}]}].map(change=>({items:[{...product(),...change}],next_cursor:null}))]) {
        assert.throws(()=>readCatalogAdminPage(malformed));
    }
    assert.deepEqual(readCatalogAdminPage(page()),page());
    const privatePage={items:[{...product(),community_count:null,communities:[]}],next_cursor:null};
    assert.deepEqual(readCatalogAdminPage(privatePage),privatePage);
});

test('invalid cursor blocks append until explicit refresh; already loaded models survive', async t => {
    let mode='first',count=0;
    t.mock.method(globalThis,'fetch',async () => {
        count++;
        if(mode==='invalid')return Response.json({detail:{code:'invalid_cursor',message:'Refresh'}},{status:422});
        return Response.json(page(mode==='refreshed'?43:42,mode==='first'?'next':null));
    });
    const resource=new PagedResource();t.after(()=>resource.dispose());
    await resource.start('admin',(cursor,signal)=>requestCatalogAdminPage('/products',{cursor,limit:24},{signal}));
    mode='invalid';await resource.loadMore();
    assert.ok(resource.getSnapshot().error instanceof PageCursorExpiredError);
    assert.deepEqual(resource.getSnapshot().items.map(item=>item.id),[42]);
    await resource.loadMore();assert.equal(count,2);
    mode='refreshed';await resource.reload();
    assert.deepEqual(resource.getSnapshot().items.map(item=>item.id),[43]);
    assert.equal(resource.getSnapshot().error,null);
});

test('private administrative reads have a deadline and respect cancellation without retry', async t => {
    t.mock.timers.enable({apis:['setTimeout']});
    const signals=[];
    t.mock.method(globalThis,'fetch',(_url,init)=>{signals.push(init.signal);return new Promise((_,reject)=>
        init.signal.addEventListener('abort',()=>reject(init.signal.reason),{once:true}))});
    const controller=new AbortController();
    const timed=requestCatalogAdminPage('/products',{},{});
    const deadline=assert.rejects(timed,{name:'TimeoutError'});
    t.mock.timers.tick(10000);await deadline;
    const cancelled=requestCatalogAdminPage('/products',{}, {signal:controller.signal});
    const rejection=assert.rejects(cancelled,{name:'AbortError'});controller.abort();await rejection;
    assert.equal(signals.length,2);assert.ok(signals.every(signal=>signal.aborted));
});
