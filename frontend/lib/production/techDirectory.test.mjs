import assert from 'node:assert/strict';
import test from 'node:test';
import {readTechCardPage,readTechCardSource,requestTechCardPage,requestTechCardModels,requestTechCardSource} from './techDirectory.ts';
import {techCardForm,techCardWrite} from './techCardEditor.ts';
import {PageCursorExpiredError} from '../catalog/pagedResource.ts';
const step={id:1,position:2,stage_code:'sewing',role_code:'qc',name:'Сохранённая операция',description:'Инструкция',standard_minutes:'12.34',labor_cost:'3.25',currency:'RUB'};
const summary={id:130,garment_model_id:230,garment_model_name:'Модель 130',code:'TECH-130',is_active:true,latest_revision_number:130,latest_revision_status:'discarded',latest_revision_name:'Отклонено',checkpoint_count:17,draft_revision_number:null};
const source={id:130,garment_model_id:230,garment_model_name:'Модель 130',code:'TECH-130',latest_revision_number:130,draft_revision_number:null,source:{id:129,revision_number:129,name_snapshot:'Рабочая версия',description_snapshot:'Сохранённое описание',checkpoints:[step]}};
const page=row=>({items:[row],next_cursor:'opaque'});
test('tech-card summaries require joined names and scalar counts instead of history',()=>{
    assert.equal(readTechCardPage(page(summary)).items[0].checkpoint_count,17);
    for(const changes of [{garment_model_name:undefined},{checkpoint_count:undefined,revisions:[]},{latest_revision_status:'unknown'},{draft_revision_number:131}])assert.throws(()=>readTechCardPage(page({...summary,...changes})));
    assert.throws(()=>readTechCardPage([summary]));
});
test('the revision source rejects another card and incomplete or duplicate operations',()=>{
    assert.equal(readTechCardSource(source,130).source.checkpoints[0].standard_minutes,'12.34');
    assert.throws(()=>readTechCardSource(source,129));
    for(const checkpoints of [[],[step,step],[{...step,labor_cost:'NaN'}],[{...step,role_code:undefined}],Array.from({length:201},(_,i)=>({...step,id:i+1,position:i+1}))])assert.throws(()=>readTechCardSource({...source,source:{...source.source,checkpoints}},130));
    assert.throws(()=>readTechCardSource({...source,source:{...source.source,revision_number:131}},130));
});
test('tech-card pages send bounded server filters and require explicit cursor recovery',async()=>{
    const previous=globalThis.fetch;
    try{
        globalThis.fetch=async(url,init)=>{const parsed=new URL(url,'https://fixture.invalid');assert.equal(parsed.pathname,'/api/production/admin/assortment/directory/tech-cards');assert.equal(parsed.searchParams.get('revision_status'),'draft');assert.equal(parsed.searchParams.get('active'),'false');assert.equal(parsed.searchParams.get('limit'),'24');assert.equal(init.cache,'no-store');return Response.json({detail:{code:'invalid_cursor'}},{status:422})};
        await assert.rejects(requestTechCardPage({revision_status:'draft',active:false,limit:24,cursor:'old'},new AbortController().signal),PageCursorExpiredError);
    }finally{globalThis.fetch=previous}
});
test('available model choices and one source use separate no-store reads without history prefetch',async()=>{
    const previous=globalThis.fetch;
    try{
        globalThis.fetch=async(url,init)=>{assert.equal(init.cache,'no-store');const parsed=new URL(url,'https://fixture.invalid');if(parsed.pathname.endsWith('/tech-card-models'))return Response.json(page({id:230,name:'Свободная модель',code:'FREE-130',is_active:false}));assert.equal(parsed.pathname,'/api/production/admin/assortment/tech-cards/130/revision-source');return Response.json(source)};
        assert.equal((await requestTechCardModels({query:'Свободная',limit:24},new AbortController().signal)).items[0].id,230);
        assert.equal((await requestTechCardSource(130,new AbortController().signal)).latest_revision_number,130);
        globalThis.fetch=async()=>Response.json({...source,id:129});await assert.rejects(requestTechCardSource(130,new AbortController().signal));
    }finally{globalThis.fetch=previous}
});
test('copying a revision preserves stored stage and role codes, decimals and user changes',()=>{
    const original=structuredClone(source),editor=techCardForm(source);
    editor.name='Исправленное название';
    const write=techCardWrite(editor);
    assert.equal(write.path,'tech-cards/130/revisions');assert.equal(write.payload.expected_latest_revision,130);
    assert.deepEqual(write.payload.revision.checkpoints,[{position:1,stage_code:'sewing',role_code:'qc',name:step.name,description:step.description,standard_minutes:12.34,labor_cost:3.25,currency:'RUB'}]);
    assert.equal(write.payload.revision.name,editor.name);assert.deepEqual(source,original);
    assert.equal('id' in write.payload.revision.checkpoints[0],false);
});
test('new cards require explicit model selection; discarded-only history starts an empty revision at its real base',()=>{
    const blank=techCardForm();assert.equal(blank.modelId,0);assert.equal(blank.checkpoints.length,1);
    blank.modelId=230;blank.code='NEW';assert.equal(techCardWrite(blank).path,'models/230/tech-cards');assert.equal('expected_latest_revision' in techCardWrite(blank).payload,false);
    const emptySource=techCardForm({...source,source:null});assert.equal(emptySource.expectedLatestRevision,130);assert.equal(emptySource.name,'');assert.equal(emptySource.checkpoints[0].name,'');
});
