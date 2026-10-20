import assert from 'node:assert/strict';
import test from 'node:test';
import {requestAdminLandingPage,readAdminLandingPage} from './adminDirectory.ts';
import {PageCursorExpiredError,PagedResource} from '../catalog/pagedResource.ts';

const row=(id=1)=>({id,version:2,title:'Коллекция',slug:'collection',image_url:null,status:'draft',partner_id:7,partner_name:'Автор',product_count:1000});
const page=(id=1,cursor=null)=>({items:[row(id)],next_cursor:cursor});
test('both administrative landing transports use bounded search, cursor, cancellation and no-store',async t=>{
    const calls=[];
    t.mock.method(globalThis,'fetch',async(url,init)=>{calls.push({url,init});return Response.json(page())});
    const signal=new AbortController().signal;
    for(const path of ['/admin/partners/landings','/production/admin/assortment/product-communities']){
        assert.equal((await requestAdminLandingPage(path,{query:'_%\\ & Ж',status:'draft',limit:24,cursor:'opaque+='},signal,path.includes('assortment')?undefined:'token')).items[0].product_count,1000);
    }
    for(const {url,init} of calls){
        const query=new URL(url,'https://test.invalid').searchParams;
        assert.equal(query.get('query'),'_%\\ & Ж');assert.equal(query.get('cursor'),'opaque+=');assert.equal(query.get('limit'),'24');assert.equal(query.get('status'),'draft');
        assert.equal(init.cache,'no-store');assert.equal(init.credentials,'same-origin');
    }
    assert.equal(new Headers(calls[0].init.headers).get('Authorization'),'Bearer token');
    assert.equal(new Headers(calls[1].init.headers).has('Authorization'),false);
});
test('legacy arrays and malformed landing summaries are visible failures',()=>{
    for(const invalid of [[],{items:[],next_cursor:''},{items:[row(),row()],next_cursor:null},
        ...[{product_count:-1},{version:0},{partner_id:0},{status:'unknown'},{image_url:{}},{partner_name:null}].map(change=>({items:[{...row(),...change}],next_cursor:null}))]){
        assert.throws(()=>readAdminLandingPage(invalid));
    }
    assert.deepEqual(readAdminLandingPage(page()),page());
});
test('landing append errors retain cards and invalid cursors require an explicit fresh page',async t=>{
    let mode='first';
    t.mock.method(globalThis,'fetch',async()=>mode==='invalid'?Response.json({detail:{code:'invalid_cursor'}},{status:422}):Response.json(page(mode==='fresh'?2:1,mode==='first'?'next':null)));
    const resource=new PagedResource();t.after(()=>resource.dispose());
    await resource.start('landings',(cursor,signal)=>requestAdminLandingPage('/admin/partners/landings',{cursor,limit:24},signal));
    mode='invalid';await resource.loadMore();
    assert.ok(resource.getSnapshot().error instanceof PageCursorExpiredError);
    assert.equal(resource.getSnapshot().items[0].id,1);
    mode='fresh';await resource.reload();assert.equal(resource.getSnapshot().items[0].id,2);
});
test('landing reads time out and do not retry automatically',async t=>{
    t.mock.timers.enable({apis:['setTimeout']});let calls=0;
    t.mock.method(globalThis,'fetch',(_url,init)=>{calls++;return new Promise((_,reject)=>init.signal.addEventListener('abort',()=>reject(init.signal.reason),{once:true}))});
    const request=requestAdminLandingPage('/admin/partners/landings',{},new AbortController().signal);
    const rejected=assert.rejects(request,{name:'TimeoutError'});t.mock.timers.tick(10000);await rejected;assert.equal(calls,1);
});
