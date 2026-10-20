import assert from 'node:assert/strict';
import test from 'node:test';
import {readModelPage,readFabricPage,readModelDetail,readRequirementPage,requestModelPage,referenceSearch} from './referenceDirectory.ts';
import {PageCursorExpiredError} from '../catalog/pagedResource.ts';
const model={id:130,category_id:1,category_name:'Категория',code:'MODEL',name:'Модель',is_active:true,base_weight_g:'500.00',size_count:2,product_count:130,tech_card_name:null,tech_card_revision:null};
const fabric={id:130,version:1,code:'FABRIC',name:'Ткань',is_active:true,color_name:'Синий',material_type:'Хлопок',color_hex:null,currency:'RUB',width_cm:'150.00',minimum_stock_meters:'15.000',density_gsm:null,cost_per_kg:'100.00',cost_per_meter:'12.34',balance:{on_hand_meters:'30.000',reserved_meters:'5.000',available_meters:'25.000',version:1,updated_at:'2026-10-18T12:00:00Z'}};
const size={id:7,code:'M',sort_order:0,version:1,currency:'RUB',allow_standard_sleeve:true,allow_height_sleeve:true,is_active:true,base_price:'80.00',base_length_cm:'72.00',base_width_cm:'64.00',min_height_cm:null,max_height_cm:null,min_length_cm:'60.00',max_length_cm:'90.00',min_width_cm:'50.00',max_width_cm:'80.00',min_sleeve_length_cm:null,max_sleeve_length_cm:null,extra_width_price_per_cm:'3.25'};
test('compact model pages reject old full arrays, duplicate records and invalid continuation',()=>{
    assert.equal(readModelPage({items:[model],next_cursor:'opaque'}).items[0].product_count,130);
    for(const value of [[model],{items:[model,model],next_cursor:null},{items:[model],next_cursor:1},{items:[{...model,size_count:undefined}],next_cursor:null}])assert.throws(()=>readModelPage(value));
});
test('fabric balances require canonical meter fields instead of silently falling back to zero',()=>{
    assert.equal(readFabricPage({items:[fabric],next_cursor:null}).items[0].balance.available_meters,'25.000');
    assert.throws(()=>readFabricPage({items:[{...fabric,balance:{available_quantity:'25'}}],next_cursor:null}));
    assert.equal(readFabricPage({items:[{...fabric,balance:null}],next_cursor:null}).items[0].balance,null);
});
test('a model cannot open for editing when its saved geometry is missing',()=>{
    const detail={...model,version:1,description:null,base_size_code:'M',fit_model_name:null,fit_model_height_cm:null,size_chart_media_object_id:null,sizes:[size]};
    assert.equal(readModelDetail(detail).sizes[0].extra_width_price_per_cm,'3.25');
    assert.throws(()=>readModelDetail({...detail,category_id:undefined}));
    assert.throws(()=>readModelDetail({...detail,description:undefined}));
    for(const field of ['base_length_cm','base_width_cm','extra_width_price_per_cm'])assert.throws(()=>readModelDetail({...detail,sizes:[{...size,[field]:undefined}]}));
});
test('requirement cards include real joined names independently of picker pages',()=>{
    const row={id:1,version:1,garment_model_id:130,fabric_id:130,garment_model_name:'Модель 130',fabric_name:'Ткань 130',meters_per_unit:'1.234',waste_percent:'2.50',is_primary:true};
    assert.equal(readRequirementPage({items:[row],next_cursor:null}).items[0].fabric_id,130);
    assert.throws(()=>readRequirementPage({items:[{...row,fabric_name:undefined}],next_cursor:null}));
});
test('directory requests preserve filters and report invalid cursors without erasing prior pages',async()=>{
    const previous=globalThis.fetch;
    try{
        globalThis.fetch=async(url,init)=>{
            const parsed=new URL(url,'https://fixture.invalid');assert.equal(parsed.pathname,'/api/production/admin/assortment/directory/models');
            assert.equal(parsed.searchParams.get('active'),'false');assert.equal(parsed.searchParams.get('category_id'),'17');assert.equal(parsed.searchParams.get('sort'),'sizes:desc');assert.equal(init.cache,'no-store');
            return Response.json({detail:{code:'invalid_cursor'}},{status:422});
        };
        await assert.rejects(requestModelPage({active:false,category_id:17,sort:'sizes:desc'},new AbortController().signal),PageCursorExpiredError);
        assert.ok(referenceSearch({query:'_%\\',cursor:'opaque'}).includes('query='));
    }finally{globalThis.fetch=previous}
});
