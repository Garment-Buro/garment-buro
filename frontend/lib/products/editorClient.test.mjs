import assert from 'node:assert/strict';
import test from 'node:test';
import {createCatalogEditorClient} from './editorClient.ts';
import {emptyPresetEditor} from '../production/presetEditor.ts';

for(const surface of ['identity','production'])test(`catalog client uses ${surface} session for detail, references and save`,async t=>{
    const calls=[],tokens=[],base=surface==='identity'?'':'/production/admin/assortment';
    t.mock.method(globalThis,'fetch',async (url,init)=>{
        calls.push({url,init});
        if(url.endsWith('/products/42'))return Response.json({...emptyPresetEditor(),id:42});
        if(url.includes('/models/130?'))return Response.json({id:130,name:'Модель',is_active:true,sizes:[{id:7,code:'M',is_active:false}]});
        if(url.includes('/selected-fabrics?'))return Response.json([129,130].map(id=>({id,name:'Ткань',is_active:false,color_name:'Белый',color_hex:null})));
        return Response.json({items:[],next_cursor:null});
    });
    const client=createCatalogEditorClient({base,options:surface==='identity'?'/catalog-editor':base+'/editor-options',
        authorize:async operation=>{const token=surface==='identity'?'staff':'';tokens.push(token);return operation(token)},
        upload:async()=>'/uploads/confirmed.webp'});
    const signal=new AbortController().signal;
    await client.detail(42,signal);
    await client.models({query:'МОДЕЛЬ_%',cursor:'101',limit:24},signal);
    await client.model(130,signal,[7]);await client.fabrics({model_id:130,limit:24},signal);
    await client.selectedFabrics([129,130],signal);await client.save(42,{title:'Current',variants:[{id:91}]});
    assert.equal(calls.length,6);assert.equal(tokens.length,6);
    assert.equal(calls[0].url,`/api${base}/products/42`);assert.ok(calls[2].url.includes('/models/130?'));
    assert.deepEqual(new URL(calls[2].url,'https://test.invalid').searchParams.getAll('selected_size_ids'),['7']);
    for(const call of calls){assert.equal(call.init.credentials,'same-origin');assert.equal(new Headers(call.init.headers).get('Authorization'),surface==='identity'?'Bearer staff':null)}
    assert.ok(calls.slice(0,5).every(call=>call.init.cache==='no-store'));
    assert.equal(new URL(calls[1].url,'https://test.invalid').searchParams.get('cursor'),'101');
    assert.equal(new URL(calls[1].url,'https://test.invalid').searchParams.get('query'),'МОДЕЛЬ_%');
    assert.deepEqual(new URL(calls[4].url,'https://test.invalid').searchParams.getAll('ids'),['129','130']);
    assert.equal(calls[5].init.method,'PUT');assert.deepEqual(JSON.parse(calls[5].init.body),{title:'Current',variants:[{id:91}]});
    assert.equal(await client.upload(new File(['test'],'test.png')),'/uploads/confirmed.webp');
});

test('editor deadlines cancel a stuck reference request without retries',async t=>{
    t.mock.timers.enable({apis:['setTimeout']});let calls=0;
    t.mock.method(globalThis,'fetch',(_url,init)=>{calls++;return new Promise((_,reject)=>init.signal.addEventListener('abort',()=>reject(init.signal.reason),{once:true}))});
    const client=createCatalogEditorClient({base:'',options:'/catalog-editor',authorize:operation=>operation('staff'),upload:async()=>''});
    const request=client.model(130,new AbortController().signal),rejected=assert.rejects(request,{name:'TimeoutError'});
    t.mock.timers.tick(10000);await rejected;assert.equal(calls,1);
});

test('successful HTTP responses still validate all editor read boundaries',async t=>{
    t.mock.method(globalThis,'fetch',async()=>Response.json({id:42,items:[],next_cursor:130}));
    const client=createCatalogEditorClient({base:'',options:'/catalog-editor',authorize:operation=>operation('staff'),upload:async()=>''});
    const signal=new AbortController().signal;
    await assert.rejects(client.detail(42,signal),/данные пресета/);
    await assert.rejects(client.model(42,signal),/данные модели пресета/);
    await assert.rejects(client.models({},signal),/страницу|продолжение/);
    await assert.rejects(client.fabrics({},signal),/страницу|продолжение/);
    await assert.rejects(client.sizes({model_id:42},signal),/страницу|продолжение/);
    await assert.rejects(client.selectedFabrics([129],signal),/выбранные ткани/);
});
