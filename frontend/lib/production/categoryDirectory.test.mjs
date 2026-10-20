import assert from 'node:assert/strict';
import test from 'node:test';
import { readCategoryPage, readModelCategory, readProductCategory, requestProductCategories, requestModelCategories } from './categoryDirectory.ts';
import { PageCursorExpiredError } from '../catalog/pagedResource.ts';
import { categorySlug } from './categoryEditor.ts';

const card={id:130,code:'saved-code',name:'Ёлка',is_active:false,version:7,item_count:130};
test('category pages require bounded scalar cards and preserve inactive selected IDs',()=>{
    assert.equal(readCategoryPage({items:[card],next_cursor:null}).items[0],card);
    for(const value of [[card],{items:[card,card],next_cursor:null},{items:[{...card,item_count:undefined}],next_cursor:null},{items:Array.from({length:101},(_,i)=>({...card,id:i+1})),next_cursor:null}])assert.throws(()=>readCategoryPage(value));
});
test('category source cannot become an empty form or silently lose product description',()=>{
    assert.equal(readModelCategory(card).code,'saved-code');
    const product={id:130,slug:'saved-address',name:'Имя',description:'Длинное описание\n'.repeat(200),version:7,is_active:false};
    assert.deepEqual(readProductCategory(product),product);
    assert.throws(()=>readProductCategory({...product,description:undefined}));
    assert.throws(()=>readModelCategory({...card,version:undefined}));
    assert.throws(()=>readModelCategory(product));
});
test('category reads keep server filters and treat changed cursor scope as an error',async t=>{
    const calls=[];t.mock.method(globalThis,'fetch',async(url,init)=>{calls.push({url,init});return calls.length===1?Response.json({items:[card],next_cursor:null}):Response.json({detail:{code:'invalid_cursor',message:'Different filters'}},{status:422})});
    const signal=new AbortController().signal;
    await requestProductCategories({query:'УЗОР_%\\',active:false,sort:'name:desc',cursor:'opaque',limit:24},signal);
    const url=new URL(calls[0].url,'https://test.invalid');assert.equal(url.pathname,'/api/production/admin/assortment/directory/categories/product-categories');assert.equal(url.searchParams.get('query'),'УЗОР_%\\');assert.equal(url.searchParams.get('active'),'false');assert.equal(url.searchParams.get('cursor'),'opaque');assert.equal(calls[0].init.cache,'no-store');
    await assert.rejects(requestModelCategories({cursor:'opaque'},signal),PageCursorExpiredError);
});
test('category address keeps the existing Cyrillic transliteration and length contract',()=>{
    assert.equal(categorySlug('  Тёплая коллекция № 2 '),'teplaya-kollekciya-2');
    assert.equal(categorySlug('saved-address'),'saved-address');assert.equal(categorySlug('😀'),'');assert.equal(categorySlug('a'.repeat(100)).length,96);
});
