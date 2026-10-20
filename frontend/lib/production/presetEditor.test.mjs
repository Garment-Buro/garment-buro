import assert from 'node:assert/strict';
import test from 'node:test';
import {buildPresetPayload,rebuildPresetVariants} from './presetEditor.ts';
const variant = {id:42,sku:'REAL-SKU',garment_size_id:7,fabric_id:9,size:'M',color:'Белый',color_hex:'#fff',
    stock_quantity:15,reserved_quantity:2,available_stock_quantity:3,width_cm:64,height_cm:72,
    preview_image:'/front.webp',images:'/front.webp,/back.webp'};

test('editing a matrix preserves matching real SKU identities, raw stock and calibrated media',()=>{
    const next = rebuildPresetVariants([variant],{sizes:[{id:7,code:'M'},{id:8,code:'L'}]},[{id:9,color_name:'Белый'}],[7,8,8],[9,9]);
    assert.equal(next.length,2);assert.equal(next[0],variant);
    assert.equal(next[1].id,0);assert.equal(next[1].garment_size_id,8);assert.equal(next[1].fabric_id,9);
    assert.equal(next[1].stock_quantity,0);
    assert.deepEqual(rebuildPresetVariants([variant],undefined,[],[],[]),[]);
});

test('historical duplicate reference pairs are preserved instead of silently dropping SKUs',()=>{
    const duplicate={...variant,id:43,sku:'OTHER-SKU',preview_image:'/other.webp'};
    assert.deepEqual(rebuildPresetVariants([variant,duplicate],undefined,[],[7],[9]),[variant,duplicate]);
});

test('matrix is bounded before expansion and includes retained duplicate SKUs in the limit',()=>{
    const ids = n => Array.from({length:n}, (_, i) => i + 1);
    assert.equal(rebuildPresetVariants([], undefined, [], ids(10), ids(20)).length, 200);
    assert.throws(() => rebuildPresetVariants([], undefined, [], ids(100), ids(100)), /200/);
    const retained = Array.from({length:200}, (_, i) => ({...variant, id:i+1}));
    assert.equal(rebuildPresetVariants(retained, undefined, [], [7], [9]).length, 200);
    assert.throws(() => rebuildPresetVariants(retained, undefined, [], [7,8], [9]), /200/);
    assert.equal(retained.length, 200);
});

test('the editor sends its current full detail, without joining references from an older list snapshot',()=>{
    const editor={id:23,version:7,title:'Изменено',slug:'latest',category_id:17,garment_model_id:88,tagsText:'спорт, лето',price:80,
        old_price:null,preset_source:'user',is_active:false,type:'normal',weight:1,height:70,width:64,length:72,
        stock_quantity:80,image_left:'/main.webp',mobile_card_image:'/mobile.webp',desktop_slider_images:'/a.webp,/b.webp',
        variants:[variant]};
    const body=buildPresetPayload(editor);
    assert.equal(body.expected_version,7);assert.equal(body.garment_model_id,88);assert.equal(body.category_id,17);assert.equal(body.slug,'latest');
    assert.equal(body.variants[0].id,42);assert.equal(body.variants[0].garment_size_id,7);assert.equal(body.variants[0].fabric_id,9);
    assert.equal(body.variants[0].stock_quantity,15);assert.equal(body.stock_quantity,80);
    assert.equal(body.variants[0].preview_image,'/front.webp');assert.equal(body.is_active,false);
    assert.equal('available_stock_quantity' in body.variants[0],false);assert.equal('sku' in body.variants[0],false);
});

test('creation never pretends to update an existing product version',()=>{
    const body=buildPresetPayload({id:0,version:1,tagsText:'',variants:[]});
    assert.equal('expected_version' in body,false);
});
