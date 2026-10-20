import assert from 'node:assert/strict';
import test from 'node:test';
import {constructorImageUrls, readConstructorProduct} from './product.ts';
import {getProductImageList} from './utils/constructor.ts';
import {constructorVariantImages} from './selection.ts';
import {constructorPublicImages} from './cartPreparation.ts';

const model = () => ({schema_version:1,id:7,title:'Реальная модель',price:80,stock_quantity:2,sizes:['M'],
    media_assets:[{id:1,url:'/uploads/front,back%20photo.webp',content_type:'image/webp'},
        {id:2,url:'https://media.test/back.webp',content_type:'image/webp'}],
    images:[{media_id:2,role:'desktop_slider_images',sort_order:1},{media_id:1,role:'desktop_slider_images',sort_order:0}],
    variants:[{id:9,size:'M',color:'green',color_hex:null,stock_quantity:2,width_cm:60,height_cm:75,
        images:[{media_id:2,role:'images',sort_order:0},{media_id:1,role:'preview_image',sort_order:0}]}]});

test('one media registry preserves comma-containing URLs, ordering and variant priority', () => {
    const value=readConstructorProduct(model(),7);
    assert.deepEqual(getProductImageList(value),['/uploads/front,back%20photo.webp','https://media.test/back.webp']);
    assert.deepEqual(constructorVariantImages(value,{size:'M',color:'green'}),['https://media.test/back.webp']);
    assert.deepEqual([...constructorPublicImages(value)],value.media_assets.map(asset=>asset.url));
    assert.equal(value.media_assets.length,2);
});

test('a preview is used only when the selected variant has no image list', () => {
    const value=model();value.variants[0].images=value.variants[0].images.slice(1);
    assert.deepEqual(constructorVariantImages(value,{size:'M',color:'green'}),['/uploads/front,back%20photo.webp']);
    assert.deepEqual(constructorVariantImages(value,{size:'M',color:'black'}),[]);
    assert.deepEqual(constructorImageUrls(value,[...value.images,...value.images],'desktop_slider_images'),getProductImageList(value));
});

test('old, incomplete, misidentified or nonfinite product responses cannot become usable models', () => {
    for(const value of [{id:7,title:'Old',price:80,desktop_slider_images:'/front.webp'},
        {...model(),schema_version:2},{...model(),id:8},{...model(),sizes:'M'},
        {...model(),stock_quantity:-1},{...model(),price:NaN},{...model(),price:Infinity},
        {...model(),variants:undefined},{...model(),images:undefined}]) assert.throws(()=>readConstructorProduct(value,7));
});

test('dangling or duplicate identities and unsupported images fail without silently dropping data', () => {
    const variants=[];
    let value=model();value.images[0].media_id=999;variants.push(value);
    value=model();value.media_assets.push(value.media_assets[0]);variants.push(value);
    value=model();value.variants.push(value.variants[0]);variants.push(value);
    value=model();value.variants[0].images[0].media_id=999;variants.push(value);
    for(const url of ['javascript:alert(1)','data:image/png;base64,aW1n','//private.test/file.webp']) {
        value=model();value.media_assets[0].url=url;variants.push(value);
    }
    value=model();value.media_assets[0].content_type='video/mp4';variants.push(value);
    for(const value of variants)assert.throws(()=>readConstructorProduct(value,7));
});
