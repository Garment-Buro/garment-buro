import assert from 'node:assert/strict';
import test from 'node:test';
import {emptyPresetEditor,buildPresetPayload} from '../production/presetEditor.ts';
import {readPresetDetail,readEditorModel,readModelOptions,readFabricOptions,readSelectedFabrics,readPresetUpload,readSizeOptions} from './editorReads.ts';

const variant=()=>({id:91,sku:'REAL-SKU',garment_size_id:7,fabric_id:129,size:'M',color:'Белый',color_hex:null,
    stock_quantity:15,reserved_quantity:4,available_stock_quantity:11,width_cm:64.25,height_cm:72.35,preview_image:'/front.webp',images:'/back.webp'});
const detail=()=>({...emptyPresetEditor(),id:42,version:7,title:'Исходный товар',stock_quantity:8,reserved_quantity:5,available_stock_quantity:3,
    image_left:'/left.webp',desktop_video:'/untouched.webm',gallery_images:'/one.webp,/two.webp',variants:[variant()]});
const model=()=>({id:130,name:'Модель',is_active:true,sizes:[{id:7,code:'M',is_active:false}]});
const fabric=id=>({id,name:`Ткань ${id}`,is_active:false,color_name:'Белый',color_hex:null});

test('preset source retains exact stock, hidden media, archived references and dimensions',()=>{
    const source=detail();assert.equal(readPresetDetail(source,42),source);
    const payload=buildPresetPayload({...source,tagsText:'тег'});
    assert.equal(payload.expected_version,7);assert.equal(payload.stock_quantity,8);
    assert.equal(payload.variants[0].stock_quantity,15);assert.equal(payload.variants[0].width_cm,64.25);
    assert.equal(payload.desktop_video,'/untouched.webm');assert.equal(payload.gallery_images,'/one.webp,/two.webp');
    assert.equal(readEditorModel(model(),130,[7]).sizes[0].is_active,false);
});

test('every consumed preset and variant field must be present, including nullable fields',()=>{
    for(const key of Object.keys(detail()).filter(key=>key!=='tagsText')){
        const row=detail();delete row[key];assert.throws(()=>readPresetDetail(row,42),undefined,`missing ${key}`);
    }
    for(const key of Object.keys(variant())){
        const row=detail();delete row.variants[0][key];assert.throws(()=>readPresetDetail(row,42),undefined,`missing variant ${key}`);
    }
});

test('preset rejects wrong identities, malformed scalars, duplicate variants and oversized source',()=>{
    for(const patch of [{id:43},{version:0},{price:'80.00'},{price:Infinity},{weight:-1},{old_price:NaN},{stock_quantity:1.5},
        {available_stock_quantity:-1},{is_active:'true'},{tags:[1]},{category_id:0},{garment_model_id:undefined},{preset_source:['user']},
        {description:8},{variants:null},{variants:[variant(),variant()]},{variants:[{...variant(),fabric_id:0}]},
        {variants:[{...variant(),width_cm:'64.25'}]},{variants:[{...variant(),stock_quantity:-1}]}]){
        assert.throws(()=>readPresetDetail({...detail(),...patch},42));
    }
    assert.throws(()=>readPresetDetail({...detail(),variants:Array.from({length:201},(_,i)=>({...variant(),id:i+1}))},42),/больше 200/);
    assert.equal(readPresetDetail({...detail(),variants:Array.from({length:200},(_,i)=>({...variant(),id:i+1}))},42).variants.length,200);
});

test('model source rejects missing size data, duplicate identities and wrong requested model',()=>{
    for(const value of [{...model(),id:129},{...model(),sizes:[{id:7,code:'M'}]},{...model(),sizes:[...model().sizes,...model().sizes]},
        {...model(),sizes:null},{...model(),is_active:null}])assert.throws(()=>readEditorModel(value,130,[7]));
});

test('selected size context is exact and size pages have independent keysets',()=>{
    assert.throws(()=>readEditorModel(model(),130,[]),/не все выбранные размеры/);
    assert.throws(()=>readEditorModel({...model(),sizes:[]},130,[7]),/не все выбранные размеры/);
    assert.throws(()=>readEditorModel(model(),130,[8]),/размерную сетку/);
    assert.equal(readEditorModel({...model(),sizes:[]},130,[]).sizes.length,0);
    const source={items:[{id:130,code:'XL',is_active:true}],next_cursor:130};
    assert.equal(readSizeOptions(source,{cursor:'129',limit:1}),source);
    for(const value of [{...source,items:[{id:130,code:'XL'}]},{...source,next_cursor:129},{...source,items:[{id:129,code:'M',is_active:true}]}])
        assert.throws(()=>readSizeOptions(value,{cursor:'129',limit:1}));
});

test('option pages enforce bounded ascending keyset responses without modifying the source',()=>{
    const page={items:[{id:130,name:'Модель',is_active:true}],next_cursor:130};
    assert.equal(readModelOptions(page,{cursor:'129',limit:1}),page);
    assert.deepEqual(readFabricOptions({items:[fabric(130)],next_cursor:null},{cursor:'129'}).items,[fabric(130)]);
    for(const value of [{items:[]},{items:[],next_cursor:130},{...page,next_cursor:131},
        {...page,items:[...page.items,...page.items]},{...page,items:[{...page.items[0],id:129}]},
        {...page,items:[{id:130,name:'Bad'}]}])assert.throws(()=>readModelOptions(value,{cursor:'129',limit:1}));
    assert.throws(()=>readFabricOptions({items:[{id:130,name:'Ткань',is_active:true,color_name:'Белый'}],next_cursor:null},{}));
});

test('selected fabrics must return exactly the requested set, allowing archives and reordered rows',()=>{
    assert.deepEqual(readSelectedFabrics([fabric(130),fabric(129)],[129,130,129]),[fabric(130),fabric(129)]);
    for(const value of [[],[fabric(129)],[fabric(129),fabric(129)],[fabric(129),fabric(131)],
        [{...fabric(129),color_hex:3},fabric(130)]])assert.throws(()=>readSelectedFabrics(value,[129,130]));
});

test('upload receipt requires persisted ID and a usable durable URL, preserving exact encoding',()=>{
    for(const url of ['/uploads/a%20b.webp','https://cdn.example.test/bucket/file.webp?v=2','http://localhost:9000/media/a.png'])
        assert.equal(readPresetUpload({id:444,url}),url);
    for(const receipt of [{url:'/unconfirmed.png'},{id:0,url:'/a.png'},{id:444},
        ...['','//example.test/a.png','data:image/png;base64,a','blob:https://example.test/id','javascript:alert(1)',
            'relative.png','https://user:password@example.test/a.png','/first.png,/second.png','/a\\b.png','/a b.png','/a\n.png']
            .map(url=>({id:444,url}))])assert.throws(()=>readPresetUpload(receipt),/не подтвердил загрузку/);
});
