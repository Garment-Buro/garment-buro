import assert from 'node:assert/strict';
import test from 'node:test';
import {readAccessoryPage,readAccessoryCategoryPage,readBoxPage,readAccessoryRequirementPage,readPackagingRulePage,requestAccessoryPage} from './stockDirectory.ts';
import {requestReferenceChoice} from './referenceDirectory.ts';
import {PageCursorExpiredError} from '../catalog/pagedResource.ts';
const common={id:130,code:'TEST',name:'Тестовая запись',is_active:true,version:1};
const accessory={...common,category_id:130,category_name:'Категория 130',model_count:130,unit_cost:'12.34',currency:'RUB',stock_quantity:25,minimum_stock_quantity:2,photo_media_object_id:null};
const box={...common,inner_length_cm:'30.25',inner_width_cm:'20.35',inner_height_cm:'10.45',max_items:7,unit_cost:'12.34',currency:'RUB',stock_quantity:25,minimum_stock_quantity:2,photo_media_object_id:null};
const page=row=>({items:[row],next_cursor:'opaque'});
test('accessory cards require an authoritative category and model count without a full link collection',()=>{
    assert.equal(readAccessoryPage(page(accessory)).items[0].model_count,130);
    assert.throws(()=>readAccessoryPage([accessory]));
    assert.throws(()=>readAccessoryPage(page({...accessory,model_count:undefined,model_ids:[1,2]})));
    assert.throws(()=>readAccessoryPage(page({...accessory,stock_quantity:-1})));
    assert.equal(readAccessoryCategoryPage(page({...common,description:'Сохранённое описание'})).items[0].description,'Сохранённое описание');
});
test('box cards preserve physical dimensions, integer capacity and exact decimal prices',()=>{
    assert.equal(readBoxPage(page(box)).items[0].inner_length_cm,'30.25');
    for(const changes of [{max_items:0},{max_items:1.5},{unit_cost:'NaN'},{inner_width_cm:undefined}])assert.throws(()=>readBoxPage(page({...box,...changes})));
});
test('rule pages carry joined names and independent box capacity instead of truncated picker lookups',()=>{
    const expense={id:130,version:1,garment_model_id:130,accessory_id:130,quantity_per_unit:'1.234',is_optional:true,notes:'Не потерять',garment_model_name:'Модель130',accessory_name:'Фурнитура130'};
    assert.equal(readAccessoryRequirementPage(page(expense)).items[0].quantity_per_unit,'1.234');
    assert.throws(()=>readAccessoryRequirementPage(page({...expense,garment_model_name:undefined})));
    const rule={id:130,version:1,garment_model_id:130,box_id:130,max_items:3,priority:0,garment_model_name:'Модель130',box_name:'Коробка130',box_capacity:7};
    assert.equal(readPackagingRulePage(page(rule)).items[0].box_capacity,7);
    assert.throws(()=>readPackagingRulePage(page({...rule,box_capacity:undefined})));
});
test('stock reads pass server filters and turn a stale cursor into explicit recovery',async()=>{
    const previous=globalThis.fetch;
    try{
        globalThis.fetch=async(url,init)=>{const parsed=new URL(url,'https://fixture.invalid');assert.equal(parsed.pathname,'/api/production/admin/assortment/directory/accessories');assert.equal(parsed.searchParams.get('category_id'),'130');assert.equal(parsed.searchParams.get('stock'),'low');assert.equal(parsed.searchParams.get('active'),'false');assert.equal(init.cache,'no-store');return Response.json({detail:{code:'invalid_cursor'}},{status:422})};
        await assert.rejects(requestAccessoryPage({category_id:130,stock:'low',active:false,cursor:'stale'},new AbortController().signal),PageCursorExpiredError);
    }finally{globalThis.fetch=previous}
});
test('the independent selected box lookup requires capacity and rejects another ID',async()=>{
    const previous=globalThis.fetch;
    try{
        globalThis.fetch=async()=>Response.json([{...common,max_items:7}]);
        assert.equal((await requestReferenceChoice('boxes',130,new AbortController().signal)).max_items,7);
        globalThis.fetch=async()=>Response.json([common]);await assert.rejects(requestReferenceChoice('boxes',130,new AbortController().signal));
        globalThis.fetch=async()=>Response.json([{...common,id:129,max_items:7}]);await assert.rejects(requestReferenceChoice('boxes',130,new AbortController().signal));
    }finally{globalThis.fetch=previous}
});
