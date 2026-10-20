import assert from 'node:assert/strict';
import test from 'node:test';
import {readAdminPartnerPage,readPartnerPayoutPage,readPartnerDashboard,readPartnerRequisites,requestAdminPartnerPage,requestPartnerPayoutPage} from './privateReads.ts';
import {PageCursorExpiredError,PagedResource} from '../catalog/pagedResource.ts';
const profile={id:1,user_id:7,code:'author',display_name:'Автор',status:'active',commission_bps:1000,created_at:'2026-10-18T10:00:00Z'};
const payout={id:2,amount:'10.01',currency:'RUB',status:'requested',created_at:'2026-10-18T10:00:00Z',note:null,paid_at:null,reviewed_at:null};
const page=(item,next_cursor=null)=>({items:[item],next_cursor});
test('private partner reads preserve search, owner authorization and bounded continuation',async t=>{
    const calls=[];
    t.mock.method(globalThis,'fetch',async(url,init)=>{calls.push({url,init});return Response.json(page(url.includes('/payouts')?payout:profile))});
    await requestAdminPartnerPage('staff',{query:'_%\\ & Ё',selectable:true,limit:24,cursor:'opaque+='});
    await requestPartnerPayoutPage('owner',{limit:24,cursor:'another'});
    for(const {url,init} of calls){assert.equal(new URL(url,'https://test').searchParams.get('limit'),'24');assert.equal(init.cache,'no-store');assert.equal(init.credentials,'same-origin')}
    const query=new URL(calls[0].url,'https://test').searchParams;
    assert.equal(query.get('query'),'_%\\ & Ё');assert.equal(query.get('selectable'),'true');assert.equal(query.get('cursor'),'opaque+=');
    assert.equal(new Headers(calls[0].init.headers).get('Authorization'),'Bearer staff');assert.equal(new Headers(calls[1].init.headers).get('Authorization'),'Bearer owner');
});
test('old truncated arrays and malformed private financial/profile data are visible errors',()=>{
    assert.deepEqual(readAdminPartnerPage(page(profile)),page(profile));assert.deepEqual(readPartnerPayoutPage(page(payout)),page(payout));
    for(const read of [readAdminPartnerPage,readPartnerPayoutPage])for(const value of [[],{items:[],next_cursor:''},{items:[],next_cursor:4}])assert.throws(()=>read(value));
    for(const delta of [{commission_bps:10001},{user_id:0},{status:'unknown'},{created_at:'not-a-date'}])assert.throws(()=>readAdminPartnerPage(page({...profile,...delta})));
    for(const delta of [{amount:'-1'},{amount:'0'},{amount:'1.001'},{currency:'USD'},{status:'unknown'},{reviewed_at:'bad'}])assert.throws(()=>readPartnerPayoutPage(page({...payout,...delta})));
    assert.throws(()=>readPartnerPayoutPage({items:[payout,payout],next_cursor:null}));
});
test('invalid payout continuation preserves the loaded history until explicit refresh',async t=>{
    let invalid=false;
    t.mock.method(globalThis,'fetch',async()=>invalid?Response.json({detail:{code:'invalid_cursor'}},{status:422}):Response.json(page(payout,'next')));
    const resource=new PagedResource();t.after(()=>resource.dispose());
    await resource.start('owner',(cursor,signal)=>requestPartnerPayoutPage('owner',{cursor,limit:24},signal));
    invalid=true;await resource.loadMore();assert.ok(resource.getSnapshot().error instanceof PageCursorExpiredError);assert.equal(resource.getSnapshot().items.length,1);
    invalid=false;await resource.reload();assert.equal(resource.getSnapshot().error,null);
});
test('partner reads time out once and honor caller cancellation',async t=>{
    t.mock.timers.enable({apis:['setTimeout']});let calls=0;
    t.mock.method(globalThis,'fetch',(_url,init)=>{calls++;return new Promise((_,reject)=>init.signal.addEventListener('abort',()=>reject(init.signal.reason),{once:true}))});
    const controller=new AbortController();const canceled=requestAdminPartnerPage('staff',{},controller.signal);const cancellation=assert.rejects(canceled,{name:'AbortError'});controller.abort();await cancellation;
    const timeout=requestPartnerPayoutPage('owner',{});const failure=assert.rejects(timeout,{name:'TimeoutError'});t.mock.timers.tick(10000);await failure;assert.equal(calls,2);
});

test('the dashboard requires an explicit bank-existence flag and bank reads distinguish null from malformed data',()=>{
    const dashboard={partner:profile,has_requisites:false,orders:0,visits:0,earned:'0.00',available:'0.00',paid:'0.00',conversion_percent:'0.00',currency:'RUB'};
    assert.equal(readPartnerDashboard(dashboard).has_requisites,false);
    assert.throws(()=>readPartnerDashboard({...dashboard,has_requisites:undefined}));
    assert.equal(readPartnerRequisites(null),null);
    for(const value of [{},{entity_type:'self_employed'},'unavailable'])assert.throws(()=>readPartnerRequisites(value));
});

test('bank read requires a positive exact server version before the form can write',()=>{
    const record={version:1,entity_type:'self_employed',recipient_name:'Получатель',tax_id:'123456789012',kpp:null,bank_name:'Банк',bic:'044525225',correspondent_account:'30101810400000000225',settlement_account:'40802810900000000001',updated_at:'2026-10-18T10:00:00Z'};
    assert.equal(readPartnerRequisites(record).version,1);
    for(const version of [undefined,null,0,-1,1.5,true,'1',2147483648])assert.throws(()=>readPartnerRequisites({...record,version}));
});
