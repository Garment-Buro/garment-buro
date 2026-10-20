import assert from 'node:assert/strict';
import test from 'node:test';
import {readPatternModels,readPatternFiles,readPatternContext,readPatternCoverage,readPatternUpload,requestPatternModels,requestPatternFiles,requestPatternSizes} from './patternDirectory.ts';
import {patternForm,patternWrite,validPatternGeometry,validMeasurement,changePatternCode,changePatternGeometry,cmCents} from './patternEditor.ts';
import {PageCursorExpiredError} from '../catalog/pagedResource.ts';
const model={id:130,name:'Модель 130',code:'MODEL-130',is_active:true,version:1};
const size={id:230,code:'M',is_active:true,version:1,min_width_cm:'50.25',max_width_cm:'550.25',min_length_cm:'60.35',max_length_cm:'560.35',allow_standard_sleeve:true,allow_height_sleeve:true};
const pattern={id:330,code:'PAT-OLD',name:'Сохранённое название',garment_model_id:130,garment_size_id:230,media_object_id:430,width_cm:'50.25',length_cm:'60.35',sleeve_variant:'standard',grid_key:'M:50.25:60.35:standard',is_active:false,version:7};
const context={model,size,pattern};
const coverage={model,size,pattern:null,step_cm:'2.00',width_values:['50.25','52.25','54.25','56.25','58.25','60.25'],length_values:['60.35','62.35','64.35','66.35','68.35','70.35'],width_page:0,length_page:0,width_pages:42,length_pages:42,width_count:251,length_count:251,required_count:'126002',uploaded_count:130,items:[pattern]};
const page=row=>({items:[row],next_cursor:'opaque'});
test('model summaries retain exact large lattice counts and file pages carry archived size labels',()=>{
    const row={...model,required_count:'15000000000000000',uploaded_count:130,pattern_count:132};
    assert.equal(readPatternModels(page(row)).items[0].required_count,'15000000000000000');
    assert.throws(()=>readPatternModels(page({...row,required_count:15000000000000000})));
    assert.throws(()=>readPatternModels(page({...row,uploaded_count:undefined,patterns:[]})));
    const file={...pattern,garment_model_name:model.name,size_code:'OLD-M',size_is_active:false};
    assert.equal(readPatternFiles(page(file)).items[0].size_is_active,false);
    assert.throws(()=>readPatternFiles(page({...file,size_code:undefined})));
});
test('coverage validates one exact 6 by 6 window and rejects duplicate or foreign cells',()=>{
    assert.equal(readPatternCoverage(coverage).items[0].media_object_id,430);
    for(const changes of [{width_values:Array(7).fill('50.25')},{width_values:['51.25',...coverage.width_values.slice(1)]},{width_pages:41},{step_cm:'1.00'},{items:[pattern,pattern]},{items:[{...pattern,garment_model_id:129}]},{items:[{...pattern,width_cm:'100.25'}]}])assert.throws(()=>readPatternCoverage({...coverage,...changes}));
});
test('editor context requires complete metadata and the file must belong to its model and size',()=>{
    assert.equal(readPatternContext(context).pattern.version,7);
    for(const changes of [{size:undefined},{size:{...size,min_width_cm:undefined}},{pattern:{...pattern,garment_size_id:231}},{pattern:{...pattern,media_object_id:0}},{model:{...model,version:undefined}}])assert.throws(()=>readPatternContext({...context,...changes}));
    assert.equal(readPatternUpload({id:430,filename:'pattern.pdf'}).id,430);
    for(const invalid of [{},{id:0},{id:430,filename:42}])assert.throws(()=>readPatternUpload(invalid));
});
test('measurements use the 2 cm lattice from fractional minima without generating its full range',()=>{
    assert.equal(cmCents('50.25'),5025);assert.equal(cmCents('99999999.99'),9999999999);
    assert.equal(validMeasurement('52.25','50.25','550.25'),true);assert.equal(validMeasurement('51.25','50.25','550.25'),false);assert.equal(validMeasurement('60.35','60.35','560.35'),true);
    assert.equal(validMeasurement('50.250','50.25','550.25'),false);assert.equal(validMeasurement('50.25',null,null),false);
    assert.equal(validPatternGeometry(patternForm(context),size),true);
});
test('editing code preserves a custom stored name, exact dimensions, media and the expected version',()=>{
    const form=changePatternCode(patternForm(context),'PAT-RENAMED'),write=patternWrite(form);
    assert.equal(write.name,pattern.name);assert.equal(write.expected_version,7);assert.equal(write.width_cm,'50.25');assert.equal(write.length_cm,'60.35');assert.equal(write.media_object_id,430);assert.equal('grid_key' in write,false);assert.equal('id' in write,false);
    const updated=changePatternGeometry(form,context,{width_cm:'52.25'});assert.equal(updated.code,'PAT-RENAMED');
});
test('new slots get a bounded code, retain explicit sleeve choice and never reuse an old file',()=>{
    const source={model:{...model,code:'MODEL-'.repeat(10)},size:{...size,code:'SIZE-'.repeat(6)},pattern:null};
    const form=patternForm(source,{width:'52.25',length:'62.35',variant:'height'});
    assert.equal(form.media_object_id,0);assert.equal(form.sleeve_variant,'height');assert.ok(form.code.length<=64);assert.ok(form.code.endsWith('-H'));
    const changed=changePatternGeometry(form,source,{width_cm:'54.25'});assert.equal(changed.name,changed.code);assert.notEqual(changed.code,form.code);assert.equal('expected_version' in patternWrite(changed),false);
});
test('pattern pages send SQL filters and scope sizes to the selected model with no-store and explicit cursor recovery',async()=>{
    const previous=globalThis.fetch,seen=[];
    try{
        globalThis.fetch=async(url,init)=>{const parsed=new URL(url,'https://fixture.invalid');seen.push(parsed);assert.equal(init.cache,'no-store');if(parsed.pathname.endsWith('/pattern-models'))return Response.json({detail:{code:'invalid_cursor'}},{status:422});return Response.json({items:[],next_cursor:null})};
        await assert.rejects(requestPatternModels({model_id:130,pattern_active:false,limit:24,cursor:'old'},new AbortController().signal),PageCursorExpiredError);
        await requestPatternFiles({model_id:130,size_id:230,limit:24},new AbortController().signal);await requestPatternSizes({model_id:130,query:'OLD',limit:24},new AbortController().signal);
        assert.equal(seen[0].searchParams.get('pattern_active'),'false');assert.equal(seen[1].searchParams.get('size_id'),'230');assert.equal(seen[2].searchParams.get('model_id'),'130');assert.ok(seen.every(url=>url.pathname.startsWith('/api/production/admin/assortment/directory/')));
    }finally{globalThis.fetch=previous}
});
