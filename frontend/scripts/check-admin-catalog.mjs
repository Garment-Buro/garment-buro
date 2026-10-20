/** Actual standalone Next/Chromium with a synthetic HTTP backend.
 * Backend RBAC, SQL arithmetic and pagination are independently covered by pytest.
 * Build with IDENTITY_SESSION_V2 and CATALOG_WRITES enabled before this gate.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {setTimeout as delay} from 'node:timers/promises';
import {chromium} from 'playwright';
import {createPatternFixture,checkPatternFlow} from './fixtures/patterns.mjs';
import {createCategoryFixture,checkCategoryFlow} from './fixtures/categories.mjs';
import {createModelEditorFixture,checkPresetOperationFlow,checkModelOperationFlow} from './fixtures/model-editor.mjs';
import {checkStorefrontLayout} from './fixtures/storefront-layout.mjs';

const source=process.cwd(),folder=fs.mkdtempSync(path.join(os.tmpdir(),'gb-admin-catalog-'));
let browser,child,upstream,currentPage;
const state={failAppend:false,invalidCursor:false,failDetail:false,customer:true,productionSession:true,productionScope:'system',failDelete:false,failSelected:true,hasRequisites:true,failReqRead:false,failReqSave:false,delayReqSave:false,failDashboardRead:false,failDashboardAfterPayout:false,balance:'100.00',failOwnerAppend:false,invalidOwnerCursor:false,failOwnerDetail:false,failProfileAppend:false,invalidProfileCursor:false,delayProfileSearch:false,failPayoutRead:false,failPayoutAppend:false,invalidPayoutCursor:false,delaySearch:false,version:7,rejectedWrites:0,failDirectoryAppend:false,invalidDirectoryCursor:false,delayDirectorySearch:false};
const directoryVersions=new Map(),directoryStatuses=new Map(),directoryWrites=[],directoryReads=[],heldDirectory=[],reads=[],held=[],writes=[],identityWrites=[],uploads=[],optionReads=[],deletes=[],landingCreates=[],ownerWrites=[],publicReads=[],profileReads=[],profileCreates=[],heldProfiles=[],payoutReads=[],reqReads=[],reqWrites=[],heldReqSaves=[],payoutWrites=[],ownerListReads=[],ownerDetailReads=[],productionAuthReads=[],productionLogins=[],productionLogouts=[],heldProductionMe=[],heldProductionLogout=[],referenceReads=[],modelDetailReads=[],modelEdits=[],fabricEdits=[],requirementEdits=[],heldReferenceSearch=[];
let bankRecord={version:1,entity_type:'self_employed',recipient_name:'Тестовый получатель',tax_id:'123456789012',kpp:null,bank_name:'Тестовый банк',bic:'044525225',correspondent_account:'30101810400000000225',settlement_account:'40802810900000000001',updated_at:'2026-10-18T10:00:00Z'};
const profiles=Array.from({length:130},(_,i)=>({id:130-i,user_id:130-i,code:`author-${130-i}`,display_name:`Автор ${String(130-i).padStart(3,'0')}`,status:(130-i)%3===0?'suspended':'active',commission_bps:1000,created_at:'2026-10-18T10:00:00Z'}));
const user={id:7,email:'admin@example.test',first_name:'Тест',phone:null,gender:null};
const product=id=>({id,title:`Модель ${String(id).padStart(3,'0')}`,slug:`model-${id}`,category_id:null,
    garment_model_id:5,category_name:null,garment_model_name:'Модель за пределами первого справочника',
    preset_source:'garment_buro',tags:[],price:'80.00',old_price:null,image_url:null,is_active:true,
    stock_quantity:3,variant_count:1000,sku:'REAL-SKU',community_count:130,communities:[{id:130,title:'Лендинг 130',slug:'landing-130'},{id:129,title:'Лендинг 129',slug:'landing-129'},{id:128,title:'Лендинг 128',slug:'landing-128'}]});
const detail=()=>({...product(1),version:state.version,slug:'fresh-detail-slug',category_id:17,garment_model_id:130,price:80,old_price:null,
    stock_quantity:8,reserved_quantity:0,available_stock_quantity:3,weight:1,height:70,width:64,length:72,
    description:'Описание',composition:'Хлопок',model_info:'Информация',sizes:'M',colors:'white',type:'special',
    video_src:'/video.webm',size_chart_img_1:'/chart-1.webp',size_chart_img_2:null,
    desktop_video:null,desktop_video_poster:'/poster.webp',desktop_card_images:null,desktop_slider_images:null,
    mobile_card_image:null,mobile_video_poster:null,mobile_slider_images:null,mobile_product_slider_images:null,mobile_size_chart_first:null,
    image_left:'/left.webp',image_right:'/right.webp',gallery_images:'/gallery.webp',
    variants:[{id:91,sku:'REAL-SKU',garment_size_id:7,fabric_id:129,size:'M',color:'Белый',color_hex:'#ffffff',
        stock_quantity:15,reserved_quantity:0,available_stock_quantity:3,width_cm:64,height_cm:72,preview_image:'/front.webp',images:'/back.webp'}]});
const all=Array.from({length:33},(_,i)=>product(i+1));
const referenceModels=new Map(),referenceFabrics=new Map();
const stockChanges=new Map(),stockReads=[],stockWrites=[],heldStockSaves=[];
const techChanges=new Map(),techReads=[],techSources=[],techWrites=[],techPublishes=[],heldTechSources=[],heldTechSaves=[],heldTechSearch=[];
const freeModel=id=>({id,name:`Свободная модель ${String(id-1000).padStart(3,'0')}`,code:`FREE-${id}`,is_active:true});
const techSummary=id=>{
    const changed=techChanges.get(id),draft=changed?changed.draft:(id%4===0?1:null),latest=changed?.latest??(id===130?130:1);
    return {id,garment_model_id:id,garment_model_name:modelRecord(id).name,code:`TECH-${String(id).padStart(3,'0')}`,is_active:true,
        latest_revision_number:latest,latest_revision_status:changed?(draft?'draft':'published'):(id===130?'discarded':draft?'draft':'published'),latest_revision_name:changed?.name??`Техкарта ${id}`,checkpoint_count:id===130?17:3,draft_revision_number:draft};
};
const stockKinds=['accessories','boxes','accessory-categories','accessory-requirements','packaging-rules'];
const stockRecord=(kind,id)=>{
    const changed=stockChanges.get(`${kind}/${id}`)??{},base={id,version:changed.version??1};
    if(kind==='accessory-categories')return {...base,code:`CATEGORY-${id}`,name:changed.name??`Категория фурнитуры ${String(id).padStart(3,'0')}`,description:`Описание категории ${id}`,is_active:true};
    const common={...base,code:`STOCK-${id}`,name:changed.name??`${kind==='boxes'?'Коробка':'Фурнитура'} ${String(id).padStart(3,'0')}`,is_active:true,unit_cost:'12.34',currency:'RUB',stock_quantity:25,minimum_stock_quantity:2,photo_media_object_id:null};
    if(kind==='accessories')return {...common,category_id:id,category_name:stockRecord('accessory-categories',id).name,model_count:130};
    if(kind==='boxes')return {...common,inner_length_cm:'30.25',inner_width_cm:'20.35',inner_height_cm:'10.45',max_items:id===129?2:7};
    if(kind==='accessory-requirements')return {...base,garment_model_id:id,accessory_id:id,garment_model_name:modelRecord(id).name,accessory_name:stockRecord('accessories',id).name,quantity_per_unit:'1.234',is_optional:true,notes:`Комментарий ${id}`};
    return {...base,garment_model_id:id,box_id:id,garment_model_name:modelRecord(id).name,box_name:stockRecord('boxes',id).name,box_capacity:stockRecord('boxes',id).max_items,max_items:id===129?2:3,priority:id%4};
};
const modelRecord=id=>({id,category_id:17,code:`MODEL-${id}`,name:referenceModels.get(id)?.name??`Модель ${String(id).padStart(3,'0')}`,version:referenceModels.get(id)?.version??1,description:'Полное описание',base_size_code:'M',fit_model_name:'Тестовая модель',fit_model_height_cm:'180.00',base_weight_g:'500.00',size_chart_media_object_id:null,is_active:true,sizes:[{id:7,code:'M',sort_order:0,base_price:'80.00',base_length_cm:'72.35',base_width_cm:'64.25',min_height_cm:'154.00',max_height_cm:'206.00',min_length_cm:'60.25',max_length_cm:'90.25',min_width_cm:'50.25',max_width_cm:'80.25',min_sleeve_length_cm:null,max_sleeve_length_cm:null,allow_standard_sleeve:true,allow_height_sleeve:true,extra_width_price_per_cm:'3.25',currency:'RUB',is_active:true,version:1},{id:8,code:'ARCHIVED',sort_order:9,base_price:'70.00',base_length_cm:'71.00',base_width_cm:'63.00',min_height_cm:null,max_height_cm:null,min_length_cm:null,max_length_cm:null,min_width_cm:null,max_width_cm:null,min_sleeve_length_cm:null,max_sleeve_length_cm:null,extra_width_price_per_cm:null,allow_standard_sleeve:true,allow_height_sleeve:true,currency:'RUB',version:1,is_active:false}]});
const fabricRecord=id=>({id,code:`FABRIC-${id}`,name:referenceFabrics.get(id)?.name??`Ткань ${String(id).padStart(3,'0')}`,material_type:'Хлопок',color_name:'Синий',color_hex:'#123456',density_gsm:'200.00',width_cm:'150.00',cost_per_kg:'100.00',cost_per_meter:'12.34',minimum_stock_meters:'15.123',currency:'RUB',is_active:true,version:referenceFabrics.get(id)?.version??1,balance:{on_hand_meters:id%2?'10.000':'30.000',reserved_meters:'5.000',available_meters:id%2?'5.000':'25.000',version:1,updated_at:'2026-10-18T12:00:00Z'}});
const json=(response,value,status=200)=>{response.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});response.end(JSON.stringify(value))};
const modelEditorFixture=createModelEditorFixture({json,modelRecord,referenceModels,detail});
const patternFixture=createPatternFixture({json,modelRecord});
const categoryFixture=createCategoryFixture({json});
const port=async()=>{const server=net.createServer();await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
    const value=server.address().port;await new Promise(ok=>server.close(ok));return value};
async function until(check,message){for(let i=0;i<160;i++){if(await check())return;await delay(50)}throw new Error(message)}
try {
    upstream=http.createServer((request,response)=>{
        const url=new URL(request.url,'https://fixture.invalid'),key=url.pathname;
        if(request.method==='GET'&&['/api/production/admin/assortment/models','/api/production/admin/assortment/patterns'].includes(key))assert.fail('Retired production list requested: '+key);
        if(modelEditorFixture.handle(request,response,url))return;
        if(patternFixture.handle(request,response,url))return;
        if(categoryFixture.handle(request,response,url))return;
        if(key==='/api/partner/dashboard')return state.failDashboardRead?json(response,{detail:'Сводка недоступна'},503):json(response,{partner:{id:7,user_id:7,code:'author',display_name:'Автор',commission_bps:1000,status:'active',created_at:'2026-10-18T10:00:00Z'},has_requisites:state.hasRequisites,conversion_percent:'0.00',orders:0,visits:0,earned:'100.00',available:state.balance,paid:'0.00',currency:'RUB'});
        if(key==='/api/partner/payouts'){
            if(request.method==='POST'){
                let body='';request.on('data',chunk=>{body+=chunk});request.on('end',()=>{const payload=JSON.parse(body);payoutWrites.push(payload);state.balance='95.00';if(state.failDashboardAfterPayout)state.failDashboardRead=true;json(response,{id:131,amount:payload.amount,currency:'RUB',status:'requested',created_at:'2026-10-18T10:00:00Z'})});return;
            }

            const query=Object.fromEntries(url.searchParams);payoutReads.push(query);assert.equal(query.limit,'24');
            if(state.failPayoutRead||query.cursor&&state.failPayoutAppend)return json(response,{detail:'Ошибка истории выплат'},503);
            if(query.cursor&&state.invalidPayoutCursor)return json(response,{detail:{code:'invalid_cursor'}},422);
            const offset=Number(query.cursor??0),rows=Array.from({length:130},(_,i)=>({id:130-i,amount:`${130-i}.01`,currency:'RUB',status:i%2?'paid':'requested',created_at:'2026-10-18T10:00:00Z',note:null,reviewed_at:null,paid_at:null}));
            return json(response,{items:rows.slice(offset,offset+24),next_cursor:rows.length>offset+24?String(offset+24):null});
        }
        if(key==='/api/partner/requisites'){
            assert.equal(request.headers.authorization,'Bearer synthetic-admin','Bank data must use the current identity session');
            if(request.method==='PUT'){
                let body='';request.on('data',chunk=>{body+=chunk});request.on('end',()=>{const payload=JSON.parse(body);reqWrites.push(payload);const send=()=>{if(state.failReqSave)return json(response,{detail:'Ошибка сохранения реквизитов'},503);if(payload.expected_version!==(bankRecord?.version??0))return json(response,{detail:{code:'requisites_version_conflict'}},409);const {expected_version,...bankFields}=payload;bankRecord={...bankFields,version:expected_version+1,updated_at:'2026-10-18T11:00:00Z'};state.hasRequisites=true;json(response,bankRecord)};if(state.delayReqSave)heldReqSaves.push(send);else send()});return;
            }
            reqReads.push(key);return state.failReqRead?json(response,{detail:'Ошибка чтения реквизитов'},503):json(response,bankRecord);
        }
        const ownLanding={id:40,partner_id:7,version:1,slug:'owner-collection',title:'Коллекция автора',headline:'Заголовок',description:'Описание',cta_label:'Выбрать модель',cta_href:'/',template_key:'light-running',content:{faq:[]},product_ids:[130,999],status:'draft'};
        if(key==='/api/partner/own-landings'){
            assert.equal(request.headers.authorization,'Bearer synthetic-admin');
            const query=Object.fromEntries(url.searchParams);ownerListReads.push(query);assert.equal(query.limit,'24');
            if(query.cursor&&state.invalidOwnerCursor)return json(response,{detail:{code:'invalid_cursor'}},422);
            if(query.cursor&&state.failOwnerAppend)return json(response,{detail:'Ошибка следующей страницы сообществ'},503);
            const rows=[...Array.from({length:129},(_,i)=>({id:1129-i,version:1,slug:`community-${1129-i}`,title:`Сообщество ${1129-i}`,image_url:null,status:'draft',product_count:2})),{id:40,version:1,slug:ownLanding.slug,title:ownLanding.title,image_url:null,status:'draft',product_count:2}],offset=Number(query.cursor??0);
            return json(response,{items:rows.slice(offset,offset+24),next_cursor:rows.length>offset+24?String(offset+24):null});
        }
        if(key==='/api/partner/own-landings/40'){
            if(request.method==='GET'){ownerDetailReads.push(key);if(state.failOwnerDetail)return json(response,{detail:'Не удалось открыть сообщество'},503)}
            if(request.method==='PATCH'){let body='';request.on('data',chunk=>{body+=chunk});request.on('end',()=>{const payload=JSON.parse(body);ownerWrites.push(payload);json(response,{...ownLanding,...payload,version:2})});return}
            return json(response,ownLanding);
        }
        if(key==='/api/catalog/products'){
            const ids=url.searchParams.getAll('ids').map(Number),query=Object.fromEntries(url.searchParams);publicReads.push({ids,...query,auth:request.headers.authorization??null});
            if(ids.length&&state.failSelected)return json(response,{detail:'Selected unavailable'},503);
            if(!ids.length&&query.cursor&&state.invalidCursor)return json(response,{detail:{code:'invalid_cursor'}},422);
            const rows=Array.from({length:130},(_,i)=>product(130-i)).filter(row=>row.id!==125&&(!ids.length||ids.includes(row.id))&&(!query.query||row.title.includes(query.query)));
            const offset=Number(query.cursor??0),limit=Number(query.limit??24);
            return json(response,{items:rows.slice(offset,offset+limit).map(row=>({...row,colors:[],source:'garment_buro',image_alt:null})),next_cursor:rows.length>offset+limit?String(offset+limit):null});
        }
        if(key==='/api/auth/refresh')return state.customer?json(response,{token:'synthetic-admin',user}):json(response,{detail:'Signed out'},401);
        if(key==='/api/production/me'){
            productionAuthReads.push(key);
            const active=state.productionSession,scope=state.productionScope;
            const send=()=>active?json(response,{id:7,name:'Тестовый администратор',stations:[],can_administer:true,admin_scope:scope}):json(response,{detail:'Signed out'},401);
            if(state.delayProductionMe)heldProductionMe.push(send);else send();return;
        }
        if(key==='/api/production/auth/login'){
            productionLogins.push(key);state.productionSession=true;
            response.setHeader('Set-Cookie','gb_production_session=synthetic-session; HttpOnly; Path=/api/production; SameSite=Strict');return json(response,{});
        }
        if(key==='/api/production/auth/logout'){
            productionLogouts.push(key);
            const send=()=>{if(state.failProductionLogout)return json(response,{detail:'Synthetic offline logout'},503);state.productionSession=false;
                response.setHeader('Set-Cookie','gb_production_session=; Max-Age=0; HttpOnly; Path=/api/production; SameSite=Strict');json(response,{})};
            if(state.delayProductionLogout)heldProductionLogout.push(send);else send();return;
        }
        if(key.endsWith('/product-counts')||key==='/api/products/counts')return json(response,{garment_buro:33,user:0,communities:key==='/api/products/counts'?null:130});
        if(key==='/api/admin/partners'){
            if(request.method==='POST'){
                let body='';request.on('data',chunk=>{body+=chunk});request.on('end',()=>{const payload=JSON.parse(body),created={id:131,user_id:131,created_at:'2026-10-18T10:00:00Z',...payload};profiles.unshift(created);profileCreates.push(created);json(response,created,201)});return;
            }
            const query=Object.fromEntries(url.searchParams);profileReads.push(query);assert.equal(query.limit,'24');
            if(query.cursor&&state.failProfileAppend)return json(response,{detail:'Ошибка продолжения партнёров'},503);
            if(query.cursor&&state.invalidProfileCursor)return json(response,{detail:{code:'invalid_cursor'}},422);
            const q=(query.query??'').toLowerCase(),rows=profiles.filter(row=>(!query.cursor||row.id<Number(query.cursor))&&(!query.status||row.status===query.status)&&(query.selectable!=='true'||row.status!=='suspended')&&(!q||(row.display_name+' '+row.code).toLowerCase().includes(q)));
            const items=rows.slice(0,24),send=()=>json(response,{items,next_cursor:rows.length>24?String(items.at(-1).id):null});
            if(state.delayProfileSearch&&q==='автор 00'){heldProfiles.push(send);return}
            return send();
        }
        if(key==='/api/admin/partners/7/landings'&&request.method==='POST'){
            let body='';request.on('data',chunk=>{body+=chunk});request.on('end',()=>{const payload=JSON.parse(body);landingCreates.push(payload);json(response,{id:131,version:1,...payload})});return;
        }
        if(/^\/api\/admin\/partners\/landings\/\d+$/.test(key)&&request.method==='PATCH'){
            let body='';request.on('data',chunk=>{body+=chunk});request.on('end',()=>{
                const payload=JSON.parse(body),id=Number(key.split('/').at(-1)),version=directoryVersions.get(id)??1;
                assert.equal(payload.expected_version,version);
                directoryWrites.push({id,payload,auth:request.headers.authorization});
                directoryVersions.set(id,version+1);directoryStatuses.set(id,payload.status);
                json(response,{id,version:version+1,status:payload.status,product_ids:[1],content:{}});
            });return;
        }
        if(key.endsWith('/product-communities')||key==='/api/admin/partners/landings'){
            const query=Object.fromEntries(url.searchParams);directoryReads.push({path:key,...query,auth:request.headers.authorization??null});
            assert.equal(query.limit,'24');
            if(query.cursor&&state.failDirectoryAppend)return json(response,{detail:'Ошибка следующей страницы лендингов'},503);
            if(query.cursor&&state.invalidDirectoryCursor)return json(response,{detail:{code:'invalid_cursor'}},422);
            const q=(query.query??'').toLowerCase();
            const rows=Array.from({length:130},(_,i)=>({id:130-i,version:directoryVersions.get(130-i)??1,title:`Лендинг ${String(130-i).padStart(3,'0')}`,
                slug:`landing-${130-i}`,image_url:null,status:directoryStatuses.get(130-i)??'draft',partner_id:7,partner_name:'Автор',product_count:1000}))
                .filter(row=>(!query.cursor||row.id<Number(query.cursor))&&row.title.toLowerCase().includes(q));
            const items=rows.slice(0,24),send=()=>json(response,{items,next_cursor:rows.length>24?String(items.at(-1).id):null});
            if(state.delayDirectorySearch&&q==='лендинг 00'){heldDirectory.push(send);return}
            return send();
        }
        if(key==='/api/production/admin/assortment/directory/selected'){
            const kind=url.searchParams.get('kind');return json(response,url.searchParams.getAll('ids').map(value=>{const id=Number(value),row=kind==='pattern-sizes'?patternFixture.choice(id):stockKinds.includes(kind)?stockRecord(kind,id):kind==='tech-card-models'?freeModel(id):kind==='models'?modelRecord(id):fabricRecord(id);return {id:row.id,name:row.name,code:row.code,is_active:row.is_active,...(kind==='boxes'?{max_items:row.max_items}:{})}}));
        }
        if(key==='/api/production/admin/assortment/directory/tech-cards'||key==='/api/production/admin/assortment/directory/tech-card-models'){
            const choices=key.endsWith('/tech-card-models'),query=Object.fromEntries(url.searchParams);techReads.push({choices,...query});assert.equal(query.limit,'24');
            if(!choices&&state.failTechRead)return json(response,{detail:'Тестовый отказ списка техкарт'},503);
            if(query.cursor&&state.failTechAppend)return json(response,{detail:'Тестовый отказ страницы техкарт'},503);
            if(query.cursor&&state.invalidTechCursor)return json(response,{detail:{code:'invalid_cursor'}},422);
            const q=(query.query??'').toLowerCase(),offset=Number(query.cursor??0);
            const rows=Array.from({length:130},(_,i)=>choices?freeModel(i+1001):techSummary(i+1)).filter(row=>(!q||[row.name,row.garment_model_name,row.code,row.latest_revision_name].some(value=>value?.toLowerCase().includes(q)))&&(!query.revision_status||row.latest_revision_status===query.revision_status));
            const send=()=>json(response,{items:rows.slice(offset,offset+24),next_cursor:rows.length>offset+24?String(offset+24):null});
            if(!choices&&state.delayTechSearch&&q==='модель 00')heldTechSearch.push(send);else send();return;
        }
        if(/^\/api\/production\/admin\/assortment\/tech-cards\/\d+\/revision-source$/.test(key)){
            const id=Number(key.split('/').at(-2));techSources.push(id);
            const send=()=>{
                if(state.failTechSource)return json(response,{detail:'Тестовый отказ исходной версии'},503);
                if(state.techSourceConflict)return json(response,{detail:'У техкарты уже есть черновик'},409);
                const checkpoints=Array.from({length:state.longTechSource?200:2},(_,i)=>({id:i+1,position:i+1,stage_code:'sewing',role_code:'qc',name:`Сохранённая операция ${i+1}`,description:`Инструкция ${i+1}`,standard_minutes:'12.34',labor_cost:'3.25',currency:'RUB'}));
                if(state.incompleteTechSource)delete checkpoints[0].labor_cost;
                return json(response,{id,garment_model_id:id,garment_model_name:modelRecord(id).name,code:`TECH-${id}`,latest_revision_number:id===130?130:1,draft_revision_number:null,source:{id:129,revision_number:id===130?129:1,name_snapshot:'Рабочая версия 129',description_snapshot:'Сохранённая инструкция',checkpoints}});
            };
            if(state.delayTechSource)heldTechSources.push(send);else send();return;
        }
        if(request.method==='POST'&&/^\/api\/production\/admin\/assortment\/tech-cards\/\d+\/revisions\/\d+\/publish$/.test(key)){
            const parts=key.split('/'),id=Number(parts.at(-4)),revision=Number(parts.at(-2));request.resume();techPublishes.push({id,revision});
            if(state.failTechPublish)return json(response,{detail:'Тестовый отказ публикации'},503);
            techChanges.set(id,{latest:revision,draft:null,name:'Опубликованная версия'});return json(response,{id:1,revision_number:revision,status:'published'});
        }
        if(request.method==='POST'&&/^\/api\/production\/admin\/assortment\/(tech-cards\/\d+\/revisions|models\/\d+\/tech-cards)$/.test(key)){
            const parts=key.split('/'),id=Number(parts.at(-2)),create=parts.at(-1)==='tech-cards';let body='';
            request.on('data',chunk=>{body+=chunk});request.on('end',()=>{const payload=JSON.parse(body);techWrites.push({id,create,payload});
                const send=()=>{if(state.failTechSave)return json(response,{detail:'Тестовый отказ сохранения техкарты'},503);if(!create){assert.equal(payload.expected_latest_revision,techSummary(id).latest_revision_number);techChanges.set(id,{latest:payload.expected_latest_revision+1,draft:payload.expected_latest_revision+1,name:payload.revision.name})}json(response,{id,revision_number:1,status:'draft'},create?201:200)};
                if(state.delayTechSave)heldTechSaves.push(send);else send();
            });return;
        }
        if(key.startsWith('/api/production/admin/assortment/directory/')&&stockKinds.includes(key.split('/').at(-1))){
            const kind=key.split('/').at(-1),query=Object.fromEntries(url.searchParams);stockReads.push({kind,...query});assert.equal(query.limit,'24');
            if(query.cursor&&state.failStockAppend)return json(response,{detail:'Тестовый отказ страницы склада'},503);
            if(query.cursor&&state.invalidStockCursor)return json(response,{detail:{code:'invalid_cursor'}},422);
            const q=(query.query??'').toLowerCase(),offset=Number(query.cursor??0);
            let rows=Array.from({length:130},(_,i)=>stockRecord(kind,i+1)).filter(row=>(!q||[row.name,row.code,row.garment_model_name,row.accessory_name,row.box_name].some(value=>value?.toLowerCase().includes(q)))&&(!query.category_id||row.category_id===Number(query.category_id)));
            if(query.stock&&query.stock!=='all')rows=rows.filter(row=>(row.stock_quantity<=row.minimum_stock_quantity)===(query.stock==='low'));
            if(query.active!==undefined)rows=rows.filter(row=>row.is_active===(query.active==='true'));
            if(kind==='accessory-requirements')rows.sort((a,b)=>b.id-a.id);
            if(kind==='packaging-rules')rows.sort((a,b)=>a.priority-b.priority||a.id-b.id);
            return json(response,{items:rows.slice(offset,offset+24),next_cursor:rows.length>offset+24?String(offset+24):null});
        }
        if(request.method==='PUT'&&/^\/api\/production\/admin\/assortment\/(accessories|boxes|accessory-categories|accessory-requirements|packaging-rules)\/\d+$/.test(key)){
            const parts=key.split('/'),id=Number(parts.at(-1)),kind=parts.at(-2);let body='';
            request.on('data',chunk=>{body+=chunk});request.on('end',()=>{const payload=JSON.parse(body);stockWrites.push({kind,id,payload});
                const send=()=>{if(state.failStockSave)return json(response,{detail:'Тестовый отказ сохранения склада'},503);assert.equal(payload.expected_version,stockRecord(kind,id).version);stockChanges.set(`${kind}/${id}`,{name:payload.name,version:payload.expected_version+1});json(response,stockRecord(kind,id))};
                if(state.delayStockSave)heldStockSaves.push(send);else send();
            });return;
        }
        if(key.startsWith('/api/production/admin/assortment/directory/')){
            const kind=key.split('/').at(-1),query=Object.fromEntries(url.searchParams);referenceReads.push({kind,...query});assert.equal(query.limit,'24');
            if(query.cursor&&state.failReferenceAppend)return json(response,{detail:'Reference append failed'},503);
            if(query.cursor&&state.invalidReferenceCursor)return json(response,{detail:{code:'invalid_cursor'}},422);
            const q=(query.query??'').toLowerCase(),offset=Number(query.cursor??0);
            let rows=Array.from({length:130},(_,i)=>{
                const id=i+1;
                if(kind==='models'){const row=modelRecord(id);return {id,category_id:17,category_name:'Категория моделей за страницей',code:row.code,name:row.name,is_active:true,base_weight_g:'500.00',size_count:1,product_count:1000,tech_card_name:null,tech_card_revision:null}}
                if(kind==='fabrics')return fabricRecord(id);
                return {id,version:1,garment_model_id:id,fabric_id:id,garment_model_name:modelRecord(id).name,fabric_name:fabricRecord(id).name,meters_per_unit:'1.234',waste_percent:'2.50',is_primary:true};
            }).filter(row=>!q||row.name.toLowerCase().includes(q));
            if(kind==='fabrics'&&query.stock&&query.stock!=='all')rows=rows.filter(row=>(Number(row.balance.available_meters)<=Number(row.minimum_stock_meters))===(query.stock==='low'));
            const send=()=>json(response,{items:rows.slice(offset,offset+24),next_cursor:rows.length>offset+24?String(offset+24):null});
            if(state.delayReferenceSearch&&q==='модель 00'){heldReferenceSearch.push(send);return}
            return send();
        }
        if(/^\/api\/production\/admin\/assortment\/models\/\d+$/.test(key)){
            const id=Number(key.split('/').at(-1));
            if(request.method==='GET'){modelDetailReads.push(id);return state.failModelRead?json(response,{detail:'Полная модель временно недоступна'},503):json(response,modelRecord(id))}
            let body='';request.on('data',chunk=>{body+=chunk});request.on('end',()=>{const payload=JSON.parse(body);modelEdits.push(payload);if(state.failModelSave)return json(response,{detail:'Тестовый отказ сохранения модели'},503);referenceModels.set(id,{name:payload.name,version:payload.expected_version+1});json(response,{...modelRecord(id),...payload,version:payload.expected_version+1})});return;
        }
        if(/^\/api\/production\/admin\/assortment\/fabrics\/\d+$/.test(key)){
            const id=Number(key.split('/').at(-1));let body='';request.on('data',chunk=>{body+=chunk});request.on('end',()=>{const payload=JSON.parse(body);fabricEdits.push(payload);referenceFabrics.set(id,{name:payload.name,version:payload.expected_version+1});json(response,{...fabricRecord(id),...payload,version:payload.expected_version+1})});return;
        }
        if(/^\/api\/production\/admin\/assortment\/fabric-requirements\/\d+$/.test(key)){
            let body='';request.on('data',chunk=>{body+=chunk});request.on('end',()=>{const payload=JSON.parse(body);requirementEdits.push(payload);json(response,{id:130,version:2,...payload})});return;
        }
        if(key.endsWith('/models')||key.endsWith('/fabrics')){
            optionReads.push({path:key,...Object.fromEntries(url.searchParams)});
            const fabrics=key.endsWith('/fabrics'),q=(url.searchParams.get('query')??'').toLowerCase();
            const list=Array.from({length:130},(_,i)=>({id:i+1,name:`${fabrics?'Ткань':'Модель'} ${String(i+1).padStart(3,'0')}`,is_active:true,
                ...(fabrics?{color_name:`Цвет ${i+1}`,color_hex:'#ffffff'}:{})})).filter(row=>row.name.toLowerCase().includes(q));
            const cursor=Number(url.searchParams.get('cursor')??0),limit=Number(url.searchParams.get('limit')??24);
            const rows=list.filter(row=>row.id>cursor),items=rows.slice(0,limit);
            return json(response,{items,next_cursor:rows.length>limit?items.at(-1).id:null});
        }
        if(key.endsWith('/editor-options/sizes')){
            optionReads.push({path:key,...Object.fromEntries(url.searchParams)});
            const cursor=Number(url.searchParams.get('cursor')??0),limit=Number(url.searchParams.get('limit')??24),q=(url.searchParams.get('query')??'').toLowerCase();
            const rows=Array.from({length:130},(_,i)=>({id:i+1,code:i===6?'M':`SIZE-${String(i+1).padStart(3,'0')}`,is_active:true})).filter(row=>row.id>cursor&&row.code.toLowerCase().includes(q));
            const items=rows.slice(0,limit);return json(response,{items,next_cursor:rows.length>limit?items.at(-1).id:null});
        }
        if(/\/models\/\d+$/.test(key))return json(response,{id:Number(key.split('/').at(-1)),name:'Модель 130',is_active:true,sizes:url.searchParams.getAll('selected_size_ids').map(Number).map(id=>({id,code:id===7?'M':`SIZE-${String(id).padStart(3,'0')}`,is_active:true}))});
        if(key.endsWith('/selected-fabrics'))return json(response,url.searchParams.getAll('ids').map(id=>({id:Number(id),name:`Ткань ${id}`,color_name:`Цвет ${id}`,color_hex:'#ffffff',is_active:true})));
        if(key==='/api/upload'||key.endsWith('/media/public')){
            request.resume();uploads.push({path:key,auth:request.headers.authorization??null});return json(response,{url:'/uploads/shared.png',id:100});
        }
        if(/^\/api\/production\/admin\/assortment\/products\/\d+$/.test(key)){
            if(request.method==='DELETE'){deletes.push(key);return state.failDelete?json(response,{detail:'Есть активный резерв'},409):json(response,{status:'deleted'})}
            const value=key.endsWith('/2')?{...detail(),id:2,garment_model_id:null,stock_quantity:7,
                variants:[{...detail().variants[0],id:92,garment_size_id:null,fabric_id:null,stock_quantity:7}]}:detail();
            if(request.method==='GET'&&state.failDetail)return json(response,{detail:'Тестовый отказ актуальной версии'},503);
            if(request.method==='PUT'){
                let body='';request.on('data',chunk=>{body+=chunk});request.on('end',()=>{const payload=JSON.parse(body);if(payload.expected_version!==state.version){state.rejectedWrites++;return json(response,{detail:{code:'catalog_product_version_conflict',message:'Товар изменился после открытия формы. Ваши правки не сохранены.'}},409)}writes.push(payload);state.version++;json(response,{...value,version:state.version})});return;
            }
            return json(response,value);
        }
        if(/^\/api\/products\/\d+$/.test(key)){
            if(state.failDetail)return json(response,{detail:'Не удалось открыть модель: тестовый отказ'},503);
            const value=key.endsWith('/2')?{...detail(),id:2,garment_model_id:null,stock_quantity:7,
                variants:[{...detail().variants[0],id:92,garment_size_id:null,fabric_id:null,stock_quantity:7}]}:detail();
            if(request.method==='PUT'){
                let body='';request.on('data',chunk=>{body+=chunk});request.on('end',()=>{const payload=JSON.parse(body);if(payload.expected_version!==state.version){state.rejectedWrites++;return json(response,{detail:{code:'catalog_product_version_conflict',message:'Товар изменился после открытия формы. Ваши правки не сохранены.'}},409)}identityWrites.push(payload);state.version++;json(response,{...value,version:state.version})});return;
            }
            return json(response,value);
        }
        if(key==='/api/products'||key==='/api/production/admin/assortment/products'){
            const query=Object.fromEntries(url.searchParams);reads.push({path:key,...query,auth:request.headers.authorization??null});
            assert.equal(query.limit,'24','Every UI request must be bounded');
            if(query.cursor&&state.invalidCursor)return json(response,{detail:{code:'invalid_cursor',message:'Обновите список.'}},422);
            if(query.cursor&&state.failAppend)return json(response,{detail:'Ошибка следующей страницы'},503);
            const sourceItems=key==='/api/products'?Array.from({length:130},(_,i)=>({...product(130-i),is_active:130-i!==125})):all;
            const items=query.query?sourceItems.filter(item=>item.title.includes(query.query)):sourceItems;
            const offset=query.cursor?Number(query.cursor):0;
            const send=()=>json(response,{items:items.slice(offset,offset+24).map(row=>key==='/api/products'?{...row,community_count:null,communities:[]}:row),next_cursor:items.length>offset+24?String(offset+24):null});
            if(state.delaySearch&&query.query==='Модель 00'){held.push(send);return}
            return send();
        }
        json(response,{detail:'Unused synthetic endpoint'},404);
    });
    await new Promise(ok=>upstream.listen(0,'127.0.0.1',ok));
    const api=`http://127.0.0.1:${upstream.address().port}`;
    fs.cpSync(path.join(source,'.next/standalone'),folder,{recursive:true,dereference:true});
    fs.cpSync(path.join(source,'.next/static'),path.join(folder,'.next/static'),{recursive:true});
    fs.cpSync(path.join(source,'public'),path.join(folder,'public'),{recursive:true});
    const file=path.join(folder,'.next/routes-manifest.json'),manifest=JSON.parse(fs.readFileSync(file,'utf8'));
    for(const group of Object.values(manifest.rewrites))if(Array.isArray(group))for(const route of group)
        if(route.source==='/api/:path*')route.destination=api+'/api/:path*';
    fs.writeFileSync(file,JSON.stringify(manifest));
    const base=`http://127.0.0.1:${await port()}`;
    child=spawn(process.execPath,['server.js'],{cwd:folder,env:{PATH:process.env.PATH,
        NODE_ENV:'production',NEXT_TELEMETRY_DISABLED:'1',PORT:new URL(base).port,HOSTNAME:'127.0.0.1',INTERNAL_API_URL:api},stdio:'ignore'});
    await until(async()=>{assert.equal(child.exitCode,null);try{return (await fetch(base+'/sw.js')).ok}catch{return false}},'Standalone not ready');
    browser=await chromium.launch({headless:true});
    const context=await browser.newContext({serviceWorkers:'block'}),page=await context.newPage(),errors=[];
    await context.addInitScript(()=>localStorage.setItem('cookieConsent','accepted'));
    currentPage=page;page.setDefaultTimeout(10000);
    page.on('pageerror',error=>errors.push(error.message));
    await context.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
    await page.goto(base+'/production');
    await until(async()=>await page.getByRole('navigation',{name:'Разделы администратора'}).count()>0,'Admin navigation not rendered: '+await page.locator('body').innerText());
    await page.getByRole('button',{name:'Пресеты',exact:true}).click();
    await page.getByText('Пресетов: 33',{exact:true}).waitFor();
    assert.equal(reads.length,0,'Overview loads counts without product cards');
    assert.equal(directoryReads.length,0,'Overview must not load landing cards or all memberships');
    await page.getByRole('button',{name:/Garment Buro Пресетов/}).click();
    const cards=page.locator('article').filter({has:page.locator('h4')});
    await until(async()=>await cards.count()===24,'First 24 cards not rendered');
    assert.ok(reads[0].path.includes('/production/'));
    await page.getByText('Модель за пределами первого справочника',{exact:true}).first().waitFor();
    assert.equal(directoryReads.length,0,'Product cards must not fetch all landing memberships');
    assert.ok((await cards.first().innerText()).includes('ещё 127'));
    await page.getByRole('button',{name:'Изменить пресет Модель 001',exact:true}).click();
    const editor=page.getByRole('dialog',{name:'Изменить пресет',exact:true});
    await editor.getByLabel('Название',{exact:true}).fill('Изменено только название');
    assert.ok(await editor.getByLabel('Название',{exact:true}).evaluate(element=>element.getBoundingClientRect().height>=48),'Production editor control styles missing');
    assert.equal(await editor.getByLabel('Slug',{exact:true}).inputValue(),'fresh-detail-slug');
    await until(async()=>await editor.getByLabel('Производственная модель',{exact:true}).inputValue()==='130','Current model outside the first page disappeared');
    for(let i=0;i<5;i++){
        await editor.getByRole('button',{name:'Ещё модели',exact:true}).click();
        await until(()=>optionReads.filter(row=>row.path.endsWith('/models')).length>=i+2,'Model continuation missing');
    }
    await until(async()=>await editor.getByRole('option',{name:'Модель 125',exact:true}).count()===1,'Models after first100 missing');
    await editor.getByRole('searchbox',{name:'Поиск ткани',exact:true}).fill('Ткань 130');
    await editor.getByRole('button',{name:'Цвет 130 · Ткань 130',exact:true}).click();
    const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRmcAAAAASUVORK5CYII=','base64');
    await editor.getByLabel('Основное изображение',{exact:true}).setInputFiles({name:'proof.png',mimeType:'image/png',buffer:png});
    await editor.getByRole('status').filter({hasText:'Изображения загружены'}).waitFor();
    for(const [width,height] of [[320,850],[390,850],[736,390],[1280,850]]){
        await page.setViewportSize({width,height});
        const layout=await editor.locator('form').evaluate(form=>{
            // The sticky action bar intentionally extends into the body padding.
            // The scroll container and its controls must still fit the actual dialog.
            const body=form.parentElement,bounds=body.getBoundingClientRect();
            const escaped=[...form.querySelectorAll('input,select,textarea,button')].filter(element=>{
                const rect=element.getBoundingClientRect();
                return rect.width>0&&(rect.right>bounds.right+1||rect.left<bounds.left-1);
            });
            return {width:body.clientWidth,scroll:body.scrollWidth,escaped:escaped.map(element=>element.getAttribute('type')||element.tagName)};
        });
        assert.ok(layout.scroll<=layout.width+1,`Shared editor scroll container overflows ${width}x${height}: ${JSON.stringify(layout)}`);
        assert.deepEqual(layout.escaped,[],`Shared editor controls leave the dialog at ${width}`);
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Editor page overflows ${width}`);
    }
    await editor.getByRole('button',{name:'Сохранить пресет',exact:true}).click();
    await until(()=>writes.length===1,'Preset write not captured');
    assert.equal(writes[0].expected_version,7);assert.equal(writes[0].slug,'fresh-detail-slug');assert.equal(writes[0].category_id,17);
    assert.equal(writes[0].variants[0].id,91);assert.equal(writes[0].variants[0].garment_size_id,7);
    assert.equal(writes[0].variants[0].fabric_id,129);assert.equal(writes[0].variants[1].fabric_id,130);assert.equal(writes[0].variants[1].id,undefined);assert.equal(writes[0].variants[0].stock_quantity,15);
    assert.equal(writes[0].image_left,'/uploads/shared.png');
    assert.equal(writes[0].stock_quantity,8);assert.equal(writes[0].image_right,'/right.webp');
    assert.equal(writes[0].variants[0].preview_image,'/front.webp');
    await until(async()=>await cards.count()===24,'List refresh after save failed');
    // A concurrent change keeps the draft, prevents repeated writes, and reloads only explicitly.
    await page.getByRole('button',{name:'Изменить пресет Модель 001',exact:true}).click();
    await editor.getByLabel('Название',{exact:true}).fill('Мой несохранённый черновик');
    state.version++;
    await editor.getByRole('button',{name:'Сохранить пресет',exact:true}).click();
    await editor.getByRole('alert').filter({hasText:'Товар изменился'}).waitFor();
    assert.equal(await editor.getByLabel('Название',{exact:true}).inputValue(),'Мой несохранённый черновик');
    assert.equal(await editor.getByRole('button',{name:'Сохранить пресет',exact:true}).isDisabled(),true);
    assert.equal(writes.length,1);
    await editor.locator('summary').filter({hasText:'Открыть актуальную версию'}).click();
    await page.setViewportSize({width:320,height:850});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Conflict page overflows on a phone');
    assert.ok(await editor.locator('form').evaluate(form=>form.parentElement.scrollWidth<=form.parentElement.clientWidth+1),'Conflict form overflows on a phone');
    state.failDetail=true;
    await editor.getByRole('button',{name:'Заменить черновик актуальной версией',exact:true}).click();
    await editor.getByRole('alert').filter({hasText:'Тестовый отказ актуальной версии'}).waitFor();
    await editor.getByRole('button',{name:'Вернуться к черновику',exact:true}).click();
    assert.equal(await editor.getByLabel('Название',{exact:true}).inputValue(),'Мой несохранённый черновик');
    assert.equal(await editor.getByRole('button',{name:'Сохранить пресет',exact:true}).isDisabled(),true);
    state.failDetail=false;
    await editor.locator('summary').filter({hasText:'Открыть актуальную версию'}).click();
    await editor.getByRole('button',{name:'Заменить черновик актуальной версией',exact:true}).click();
    await until(async()=>await editor.getByLabel('Название',{exact:true}).inputValue()==='Модель 001','Latest version not loaded');
    await editor.getByLabel('Название',{exact:true}).fill('Правки после обновления');
    const expectedProductionVersion=state.version;
    await editor.getByRole('button',{name:'Сохранить пресет',exact:true}).click();
    await until(()=>writes.length===2,'Reloaded production editor did not save');
    assert.equal(writes[1].expected_version,expectedProductionVersion);
    await until(async()=>await editor.count()===0,'Editor did not close');
    state.failAppend=true;
    await page.getByRole('button',{name:'Загрузить ещё',exact:true}).click();
    await page.getByText('Ошибка следующей страницы',{exact:true}).waitFor();
    assert.equal(await cards.count(),24,'Append failure retains cards');
    state.failAppend=false;
    await page.getByRole('button',{name:'Загрузить ещё',exact:true}).click();
    await until(async()=>await cards.count()===33,'Append retry not rendered');
    const search=page.getByRole('searchbox',{name:'Поиск пресета'});
    state.delaySearch=true;await search.fill('Модель 00');
    await until(()=>held.length===1,'Delayed search never started');
    await search.fill('Модель 033');
    await until(async()=>await cards.count()===1&&await cards.first().innerText().then(text=>text.includes('033')),'New search not rendered');
    held.splice(0).forEach(send=>send());await delay(200);
    assert.equal(await cards.count(),1,'Late search must not replace the newer result');
    await page.getByRole('button',{name:/Фильтры/}).click();
    await page.getByRole('radio',{name:'Скрытые',exact:true}).check();
    await page.getByRole('radio',{name:'Нет в наличии',exact:true}).check();
    await page.getByRole('radio',{name:'Сначала дороже',exact:true}).check();
    await page.getByRole('button',{name:'Показать',exact:true}).click();
    await until(()=>reads.some(read=>read.active==='false'&&read.stock==='empty'&&read.sort==='price:desc'),'Filters never reached backend');
    // Cursor failure has a refresh action, never a misleading load-more button.
    await search.fill('');await until(async()=>await cards.count()===24,'Filter page not rendered');
    state.invalidCursor=true;
    await page.getByRole('button',{name:'Загрузить ещё',exact:true}).click();
    await page.getByText('Список изменился. Обновите его, чтобы продолжить.',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Загрузить ещё',exact:true}).count(),0);
    state.invalidCursor=false;
    await page.getByRole('button',{name:'Обновить список',exact:true}).click();
    await until(async()=>await cards.count()===24,'Refresh after invalid cursor failed');
    for(const width of [320,390,736,1280]){
        await page.setViewportSize({width,height:850});
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Overflow at ${width}`);
    }
    await page.getByRole('button',{name:'Все пресеты',exact:true}).click();
    await page.getByRole('button',{name:/Пресеты по лендингам Лендингов/}).click();
    const communityCards=page.getByRole('button').filter({has:page.getByText(/^Лендинг \d{3}$/, {exact:true})});
    await until(async()=>await communityCards.count()===24,'First landing page not rendered');
    state.failDirectoryAppend=true;
    await page.getByRole('button',{name:'Ещё лендинги',exact:true}).click();
    await page.getByText('Ошибка следующей страницы лендингов',{exact:true}).waitFor();
    assert.equal(await communityCards.count(),24);
    state.failDirectoryAppend=false;
    await page.getByRole('button',{name:'Ещё лендинги',exact:true}).click();
    await until(async()=>await communityCards.count()===48,'Landing append recovery failed');
    while(await page.getByRole('button',{name:'Ещё лендинги',exact:true}).count()){
        const before=await communityCards.count();
        await page.getByRole('button',{name:'Ещё лендинги',exact:true}).click();
        await until(async()=>await communityCards.count()>before,'Landing continuation failed');
    }
    assert.equal(await communityCards.count(),130);
    const landingSearch=page.getByRole('searchbox',{name:'Поиск лендинга',exact:true});
    state.delayDirectorySearch=true;
    await landingSearch.fill('Лендинг 00');await until(()=>heldDirectory.length===1,'Delayed landing search not issued');
    await landingSearch.fill('Лендинг 130');
    await until(async()=>await communityCards.count()===1,'New landing search not rendered');
    heldDirectory.splice(0).forEach(send=>send());await delay(200);
    assert.equal(await communityCards.count(),1);
    await communityCards.first().click();
    await until(()=>reads.some(row=>row.community_id==='130'&&row.source==='all'),'Selected landing never reached product filter');
    await until(async()=>await cards.count()===24,'Selected landing product page not rendered');
    await page.getByRole('heading',{name:'Лендинг 130',exact:true}).waitFor();
    await page.goto(base+'/admin/models');
    await page.getByRole('heading',{name:'Пресеты',exact:true}).waitFor();
    assert.equal(new URL(page.url()).pathname,'/production');
    assert.equal(new URL(page.url()).searchParams.get('section'),'presets');
    await page.getByRole('button',{name:/Garment Buro Пресетов/}).click();
    await page.getByRole('button',{name:'Удалить пресет Модель 001',exact:true}).click();
    let removal=page.getByRole('dialog',{name:'Удалить пресет',exact:true});
    await removal.getByRole('button',{name:'Отмена',exact:true}).click();
    assert.equal(deletes.length,0);
    await page.getByRole('button',{name:'Удалить пресет Модель 001',exact:true}).click();
    removal=page.getByRole('dialog',{name:'Удалить пресет',exact:true});
    state.failDelete=true;await removal.getByRole('button',{name:'Удалить окончательно',exact:true}).click();
    await removal.getByRole('alert').filter({hasText:'Есть активный резерв'}).waitFor();
    assert.equal(await cards.count(),24);
    state.failDelete=false;await removal.getByRole('button',{name:'Удалить окончательно',exact:true}).click();
    await until(async()=>await removal.count()===0,'Delete did not close after successful retry');
    assert.equal(deletes.length,2);
    state.failDetail=true;
    await page.goto(base+'/admin/products/1/edit');
    await page.getByRole('alert').filter({hasText:'Тестовый отказ'}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Сохранить пресет',exact:true}).count(),0,'Failed detail must not open an empty editable model');
    state.failDetail=false;await page.getByRole('button',{name:'Повторить',exact:true}).click();
    await page.getByRole('button',{name:'Сохранить пресет',exact:true}).waitFor();
    assert.equal(await page.getByRole('dialog',{name:'Изменить пресет',exact:true}).getByLabel('Название',{exact:true}).inputValue(),'Модель 001');
    const staffEditor=page.getByRole('dialog',{name:'Изменить пресет',exact:true});
    assert.ok(await staffEditor.getByLabel('Название',{exact:true}).evaluate(element=>element.getBoundingClientRect().height>=48),'Redirected production editor control styles missing');
    await staffEditor.getByLabel('Основное изображение',{exact:true}).setInputFiles({name:'staff.png',mimeType:'image/png',buffer:png});
    await staffEditor.getByRole('status').filter({hasText:'Изображения загружены'}).waitFor();
    assert.ok(uploads.some(row=>row.path.endsWith('/media/public')&&row.auth===null));
    const presetOperationProof=await checkPresetOperationFlow(page,{fixture:modelEditorFixture,png});
    await page.goto(base+'/admin/products/2/edit');
    const physical=page.getByRole('dialog',{name:'Изменить пресет',exact:true});
    await physical.getByLabel('Физический остаток товара',{exact:true}).waitFor();
    assert.equal(await physical.getByLabel('Физический остаток товара',{exact:true}).inputValue(),'7');
    await physical.getByLabel('Название',{exact:true}).fill('Физический товар');
    state.version++;
    await physical.getByRole('button',{name:'Сохранить пресет',exact:true}).click();
    await physical.getByRole('alert').filter({hasText:'Товар изменился'}).waitFor();
    assert.equal(await physical.getByLabel('Название',{exact:true}).inputValue(),'Физический товар');
    assert.equal(writes.length,2);
    assert.equal(await physical.getByRole('button',{name:'Сохранить пресет',exact:true}).isDisabled(),true);
    await physical.locator('summary').filter({hasText:'Открыть актуальную версию'}).click();
    await physical.getByRole('button',{name:'Заменить черновик актуальной версией',exact:true}).click();
    await until(async()=>await physical.getByLabel('Название',{exact:true}).inputValue()==='Модель 001','Redirected latest version not loaded');
    const expectedIdentityVersion=state.version;
    await physical.getByRole('button',{name:'Сохранить пресет',exact:true}).click();
    await until(()=>writes.length===3,'Redirected production editor did not save');
    assert.equal(writes[2].expected_version,expectedIdentityVersion);assert.equal(state.rejectedWrites,2);
    assert.equal(writes[2].garment_model_id,null);assert.equal(writes[2].stock_quantity,7);
    assert.equal(writes[2].variants[0].id,92);assert.equal(writes[2].variants[0].stock_quantity,7);
    await page.goto(base+'/admin/partners');
    const staffLandingCards=page.locator('article').filter({has:page.getByRole('heading',{level:3,name:/^Лендинг /})});
    await until(async()=>await staffLandingCards.count()===24,'Staff landing directory not rendered');
    assert.ok(directoryReads.some(row=>row.path==='/api/admin/partners/landings'&&row.auth==='Bearer synthetic-admin'));
    state.invalidDirectoryCursor=true;
    await page.getByRole('button',{name:'Ещё лендинги',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'Список изменился'}).waitFor();
    assert.equal(await staffLandingCards.count(),24);
    assert.equal(await page.getByRole('button',{name:'Ещё лендинги',exact:true}).count(),0);
    state.invalidDirectoryCursor=false;
    await page.getByRole('button',{name:'Обновить лендинги',exact:true}).click();
    await until(async()=>await staffLandingCards.count()===24,'Staff landing refresh failed');
    await page.getByRole('searchbox',{name:'Поиск лендинга',exact:true}).fill('Лендинг 001');
    await until(async()=>await staffLandingCards.count()===1,'Staff landing search after first100 failed');
    assert.ok((await staffLandingCards.first().innerText()).includes('Лендинг 001'));
    await staffLandingCards.first().getByRole('button',{name:'Опубликовать',exact:true}).click();
    await until(async()=>await staffLandingCards.first().getByRole('button',{name:'Снять с публикации',exact:true}).count()===1,'Publication status did not refresh from the directory');
    assert.deepEqual(directoryWrites[0],{id:1,payload:{expected_version:1,status:'published'},auth:'Bearer synthetic-admin'});
    await staffLandingCards.first().getByRole('button',{name:'Снять с публикации',exact:true}).click();
    await until(async()=>await staffLandingCards.first().getByRole('button',{name:'Опубликовать',exact:true}).count()===1,'Unpublish did not use the refreshed summary version');
    assert.deepEqual(directoryWrites[1].payload,{expected_version:2,status:'draft'});
    for(const width of [320,390,736]){
        await page.setViewportSize({width,height:850});
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Staff directory page overflows at ${width}`);
    }

    const form=page.locator('form').filter({has:page.getByRole('heading',{name:'Новый лендинг',exact:true})});
    const picker=form.locator('fieldset').filter({has:page.getByRole('searchbox',{name:'Найти модель в каталоге',exact:true})}).last();
    await until(async()=>await picker.getByRole('checkbox').count()===24,'Admin picker first page missing');
    const row=id=>picker.locator('label').filter({has:page.getByText(`Модель ${String(id).padStart(3,'0')}`,{exact:true})});
    await row(130).getByRole('checkbox').check();
    state.failAppend=true;await picker.getByRole('button',{name:'Ещё модели',exact:true}).click();
    await picker.getByRole('alert').waitFor();
    assert.equal(await picker.getByRole('checkbox').count(),24);
    state.failAppend=false;await picker.getByRole('button',{name:'Ещё модели',exact:true}).click();
    await until(async()=>await picker.getByRole('checkbox').count()===48,'Picker append recovery missing');
    while(await picker.getByRole('button',{name:'Ещё модели',exact:true}).count()){
        const before=await picker.getByRole('checkbox').count();
        await picker.getByRole('button',{name:'Ещё модели',exact:true}).click();
        await until(async()=>await picker.getByRole('checkbox').count()>before,'Picker continuation missing');
    }
    assert.equal(await picker.getByRole('checkbox').count(),130);
    await row(1).getByRole('checkbox').check();
    const chosen=picker.getByRole('list',{name:'Модели коллекции',exact:true});
    assert.deepEqual(await chosen.locator('li > span').allTextContents(),['Модель 130','Модель 001']);
    await picker.getByRole('button',{name:'Поднять модель 1',exact:true}).click();
    const pickerSearch=picker.getByRole('searchbox',{name:'Найти модель в каталоге',exact:true});
    state.delaySearch=true;await pickerSearch.fill('Модель 00');
    await until(()=>held.length===1,'Picker delayed search not issued');
    await pickerSearch.fill('Модель 125');
    await until(async()=>await picker.getByRole('checkbox').count()===1,'Picker latest search missing');
    held.splice(0).forEach(send=>send());await delay(200);
    assert.equal(await picker.getByRole('checkbox').count(),1);
    assert.deepEqual(await chosen.locator('li > span').allTextContents(),['Модель 001','Модель 130']);
    await row(125).getByRole('checkbox').check();
    assert.ok((await row(125).innerText()).includes('Скрыта'));
    await pickerSearch.fill('');await until(async()=>await picker.getByRole('checkbox').count()===24,'Picker query reset missing');
    state.invalidCursor=true;await picker.getByRole('button',{name:'Ещё модели',exact:true}).click();
    await picker.getByRole('alert').waitFor();
    assert.equal(await picker.getByRole('button',{name:'Ещё модели',exact:true}).count(),0);
    assert.equal(await chosen.locator('li').count(),3);
    state.invalidCursor=false;await picker.getByRole('button',{name:'Повторить',exact:true}).click();
    await until(async()=>await picker.getByRole('checkbox').count()===24,'Picker refresh missing');
    // Select 50 across pages, then verify the server limit is enforced before submit.
    for(let n=0;n<3;n++){
        for(const checkbox of await picker.getByRole('checkbox').all()){
            if(!await checkbox.isChecked()&&!await checkbox.isDisabled())await checkbox.check();
        }
        if(n<2){const before=await picker.getByRole('checkbox').count();await picker.getByRole('button',{name:'Ещё модели',exact:true}).click();await until(async()=>await picker.getByRole('checkbox').count()>before,'Picker cap continuation missing')}
    }
    assert.equal(await chosen.locator('li').count(),50);
    assert.ok(await picker.getByRole('checkbox').evaluateAll(nodes=>nodes.filter(n=>!n.checked).every(n=>n.disabled)));
    // Return to our ordered three IDs and save the actual form payload.
    const removeLabels=await chosen.locator('button[aria-label^="Убрать модель "]').evaluateAll(nodes=>nodes.map(node=>node.getAttribute('aria-label')));
    for(const label of removeLabels){
        if(!['Убрать модель 1','Убрать модель 130','Убрать модель 125'].includes(label))await chosen.getByRole('button',{name:label,exact:true}).click();
    }
    const beforeSave=await chosen.locator('button[aria-label^="Убрать модель "]').evaluateAll(nodes=>nodes.map(node=>Number(node.getAttribute('aria-label').split(' ').at(-1))));
    assert.deepEqual(beforeSave,[1,130,125]);
    await form.getByRole('searchbox',{name:'Найти партнёра',exact:true}).fill('Автор 007');
    await form.getByRole('option',{name:'Автор 007 · author-7',exact:true}).waitFor({state:'attached'});
    await form.getByRole('combobox',{name:'Партнёр',exact:true}).selectOption('7');
    await form.getByLabel('Адрес страницы',{exact:true}).fill('picker-proof');
    await form.getByLabel('SEO название',{exact:true}).fill('Проверка коллекции');
    await form.getByLabel('Главный заголовок',{exact:true}).fill('Коллекция');
    await form.getByLabel('Описание',{exact:true}).fill('Описание коллекции');
    for(const width of [320,390,736]){await page.setViewportSize({width,height:850});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Picker overflows at ${width}`)}
    if(process.env.GB_ADMIN_PROOF_DIR){await pickerSearch.fill('Модель 125');await until(async()=>await picker.getByRole('checkbox').count()===1,'Screenshot search missing');await picker.screenshot({path:path.join(process.env.GB_ADMIN_PROOF_DIR,'admin-product-picker.png')})}
    await form.getByRole('button',{name:'Сохранить черновик',exact:true}).click();
    await until(()=>landingCreates.length===1,'Selected product IDs were not saved');
    assert.deepEqual(landingCreates[0].product_ids,beforeSave);
    await until(async()=>await picker.getByRole('list',{name:'Модели коллекции',exact:true}).count()===0,'Picker did not reset after save');
    assert.ok(reads.some(read=>read.path==='/api/products'&&read.auth==='Bearer synthetic-admin'));
    assert.equal(identityWrites.length,0,'Retired editor must not issue identity product writes');
    const partnerDirectory=page.getByRole('region',{name:'Справочник партнёров',exact:true});
    const partnerRows=partnerDirectory.getByRole('article');
    await until(async()=>await partnerRows.count()===24,'Profile directory first24 missing');
    state.failProfileAppend=true;await partnerDirectory.getByRole('button',{name:'Ещё партнёры',exact:true}).click();
    await partnerDirectory.getByRole('alert').filter({hasText:'Ошибка продолжения партнёров'}).waitFor();
    assert.equal(await partnerRows.count(),24);
    state.failProfileAppend=false;await partnerDirectory.getByRole('button',{name:'Ещё партнёры',exact:true}).click();
    await until(async()=>await partnerRows.count()===48,'Profile append recovery missing');
    while(await partnerDirectory.getByRole('button',{name:'Ещё партнёры',exact:true}).count()){
        const before=await partnerRows.count();await partnerDirectory.getByRole('button',{name:'Ещё партнёры',exact:true}).click();await until(async()=>await partnerRows.count()>before,'Profile continuation missing');
    }
    assert.equal(await partnerRows.count(),130);
    const directorySearch=partnerDirectory.getByRole('searchbox',{name:'Поиск партнёров',exact:true});
    state.delayProfileSearch=true;await directorySearch.fill('Автор 00');await until(()=>heldProfiles.length===1,'Delayed profile search missing');
    await directorySearch.fill('Автор 001');await until(async()=>await partnerRows.count()===1,'Latest profile search missing');
    heldProfiles.splice(0).forEach(send=>send());await delay(200);assert.equal(await partnerRows.count(),1);
    await directorySearch.fill('');await until(async()=>await partnerRows.count()===24,'Profile reset missing');
    state.invalidProfileCursor=true;await partnerDirectory.getByRole('button',{name:'Ещё партнёры',exact:true}).click();
    await partnerDirectory.getByRole('alert').filter({hasText:'Список изменился'}).waitFor();
    assert.equal(await partnerDirectory.getByRole('button',{name:'Ещё партнёры',exact:true}).count(),0);
    state.invalidProfileCursor=false;await partnerDirectory.getByRole('button',{name:'Обновить партнёров',exact:true}).click();
    await until(async()=>await partnerRows.count()===24,'Profile cursor refresh missing');
    await partnerDirectory.getByRole('combobox',{name:/Статус партнёра/}).selectOption('suspended');
    await until(()=>profileReads.some(row=>row.status==='suspended'),'Profile status filter never reached backend');
    await until(async()=>await partnerRows.count()===24,'Profile status rows missing');
    assert.ok((await partnerRows.allTextContents()).every(text=>text.includes('Доступ приостановлен')));
    // A new confirmed profile remains selected when an older search finally returns.
    const ownerSearch=form.getByRole('searchbox',{name:'Найти партнёра',exact:true});
    await ownerSearch.fill('Автор 00');await until(()=>heldProfiles.length===1,'Pending selector search missing');
    state.delayProfileSearch=false;
    const createProfile=page.locator('form').filter({has:page.getByRole('heading',{name:'Новый партнёр',exact:true})});
    await createProfile.getByLabel('Почта',{exact:true}).fill('created@example.test');
    await createProfile.getByLabel('Код партнёра',{exact:true}).fill('created-author');
    await createProfile.getByLabel('Имя для кабинета',{exact:true}).fill('Новый автор');
    await createProfile.getByRole('button',{name:'Создать партнёра',exact:true}).click();
    await until(()=>profileCreates.length===1,'Profile creation missing');
    await until(async()=>await form.getByRole('combobox',{name:'Партнёр',exact:true}).inputValue()==='131','Created owner not selected');
    heldProfiles.splice(0).forEach(send=>send());await delay(200);
    assert.equal(await form.getByRole('combobox',{name:'Партнёр',exact:true}).inputValue(),'131');
    await ownerSearch.fill('Автор 130');
    await form.getByRole('option',{name:'Автор 130 · author-130',exact:true}).waitFor({state:'attached'});
    assert.equal(await form.getByRole('combobox',{name:'Партнёр',exact:true}).inputValue(),'131');
    assert.equal(await form.getByRole('option',{name:/Доступ приостановлен/}).count(),0);
    await ownerSearch.fill('');
    const selectorOptions=form.getByRole('combobox',{name:'Партнёр',exact:true}).locator('option');
    await until(async()=>await selectorOptions.count()===25,'Selector first24 missing');
    while(await form.getByRole('button',{name:'Ещё партнёры',exact:true}).count()){
        const before=await selectorOptions.count();await form.getByRole('button',{name:'Ещё партнёры',exact:true}).click();await until(async()=>await selectorOptions.count()>before,'Selector continuation missing');
    }
    assert.equal(await selectorOptions.count(),89);
    assert.equal(await form.locator('option[value="129"]').count(),0,'Suspended partner must not be selectable');
    assert.equal(await form.getByRole('combobox',{name:'Партнёр',exact:true}).inputValue(),'131');

    for(const width of [320,390,736]){await page.setViewportSize({width,height:850});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Partner directory overflows at ${width}`)}
    if(process.env.GB_ADMIN_PROOF_DIR)await partnerDirectory.screenshot({path:path.join(process.env.GB_ADMIN_PROOF_DIR,'partner-directory.png')});
    await page.goto(base+'/admin/products/new');
    await page.getByRole('dialog',{name:'Новый пресет',exact:true}).waitFor();
    assert.equal(new URL(page.url()).pathname,'/production');
    state.failPayoutRead=true;
    await page.goto(base+'/partner');
    const payoutHistory=page.getByRole('region',{name:'История выплат',exact:true});
    const payoutRows=payoutHistory.getByRole('article');
    await payoutHistory.getByRole('alert').filter({hasText:'Ошибка истории выплат'}).waitFor();
    await page.getByRole('heading',{name:'Управление выплатами',exact:true}).waitFor();
    state.failPayoutRead=false;await payoutHistory.getByRole('button',{name:'Обновить выплаты',exact:true}).click();
    await until(async()=>await payoutRows.count()===3,'Payout preview missing');
    await payoutHistory.getByRole('button',{name:'Все',exact:true}).click();
    await until(async()=>await payoutRows.count()===24,'Payout expansion missing');
    state.invalidPayoutCursor=true;await payoutHistory.getByRole('button',{name:'Ещё выплаты',exact:true}).click();
    await payoutHistory.getByRole('alert').filter({hasText:'Список изменился'}).waitFor();
    assert.equal(await payoutHistory.getByRole('button',{name:'Ещё выплаты',exact:true}).count(),0);
    assert.equal(await payoutRows.count(),24);
    state.invalidPayoutCursor=false;await payoutHistory.getByRole('button',{name:'Обновить выплаты',exact:true}).click();
    await until(async()=>await payoutRows.count()===24,'Payout cursor refresh missing');
    state.failPayoutAppend=true;await payoutHistory.getByRole('button',{name:'Ещё выплаты',exact:true}).click();
    await payoutHistory.getByRole('alert').waitFor();assert.equal(await payoutRows.count(),24);
    state.failPayoutAppend=false;await payoutHistory.getByRole('button',{name:'Ещё выплаты',exact:true}).click();
    await until(async()=>await payoutRows.count()===48,'Payout append recovery missing');
    while(await payoutHistory.getByRole('button',{name:'Ещё выплаты',exact:true}).count()){
        const before=await payoutRows.count();await payoutHistory.getByRole('button',{name:'Ещё выплаты',exact:true}).click();await until(async()=>await payoutRows.count()>before,'Payout continuation missing');
    }
    assert.equal(await payoutRows.count(),130);
    await payoutHistory.getByRole('button',{name:'Свернуть',exact:true}).click();assert.equal(await payoutRows.count(),3);
    for(const width of [320,390,736]){await page.setViewportSize({width,height:850});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Payout history overflows at ${width}`)}
    if(process.env.GB_ADMIN_PROOF_DIR)await payoutHistory.screenshot({path:path.join(process.env.GB_ADMIN_PROOF_DIR,'partner-payouts.png')});
    assert.equal(reqReads.length,0,'Closed cabinet must not request decrypted bank data');
    const requisites=page.getByRole('region',{name:'Реквизиты',exact:true});
    const toggleReq=requisites.getByRole('button',{name:/Реквизиты/});
    state.failReqRead=true;await toggleReq.click();
    await requisites.getByRole('alert').filter({hasText:'Не удалось загрузить реквизиты'}).waitFor();
    assert.equal(await requisites.getByRole('form').count(),0,'Failed read must not open empty editable bank details');
    await page.getByRole('heading',{name:'Мои сообщества',exact:true}).waitFor();
    state.failReqRead=false;await requisites.getByRole('button',{name:'Повторить загрузку реквизитов',exact:true}).click();
    const recipient=requisites.getByRole('textbox',{name:'Получатель',exact:true});await recipient.waitFor();
    assert.equal(await recipient.inputValue(),'Тестовый получатель');
    await recipient.fill('Новый получатель');
    const saveReq=requisites.getByRole('button',{name:'Сохранить реквизиты',exact:true});
    state.failReqSave=true;state.delayReqSave=true;await saveReq.click();
    await until(()=>heldReqSaves.length===1,'Bank save not captured');
    assert.equal(await recipient.isDisabled(),true);assert.equal(await toggleReq.isDisabled(),true);
    assert.equal(await requisites.getByRole('button',{name:'Сохраняем…',exact:true}).isDisabled(),true);
    heldReqSaves.splice(0).forEach(send=>send());
    await requisites.getByRole('alert').filter({hasText:'Не удалось сохранить реквизиты'}).waitFor();
    assert.equal(await recipient.inputValue(),'Новый получатель');
    state.failReqSave=false;state.delayReqSave=false;state.failDashboardRead=true;
    await saveReq.click();await requisites.getByRole('status').filter({hasText:'Реквизиты сохранены'}).waitFor();
    await page.getByRole('alert').filter({hasText:'Не удалось обновить сводку'}).waitFor();
    assert.equal(reqWrites.length,2);assert.equal(reqWrites[1].recipient_name,'Новый получатель');
    assert.equal(reqWrites[1].expected_version,1);assert.equal(reqWrites[1].version,undefined);assert.equal(reqWrites[1].updated_at,undefined);assert.equal(reqWrites[1].partner_id,undefined);
    state.failDashboardRead=false;await page.getByRole('button',{name:'Обновить сводку',exact:true}).click();
    const finance=page.getByRole('region',{name:'Доступно к выводу',exact:true});
    await until(async()=>await finance.getByRole('button',{name:'Вывести деньги',exact:true}).isEnabled(),'Financial refresh did not recover');
    assert.equal(reqWrites.length,2,'Refreshing a failed summary must not save bank data again');
    await recipient.fill('Несохранённый черновик');await toggleReq.click();await toggleReq.click();
    assert.equal(await recipient.inputValue(),'Несохранённый черновик');assert.equal(reqReads.length,2);
    // Another tab has already saved: the stale draft must not overwrite it.
    bankRecord={...bankRecord,version:bankRecord.version+1,recipient_name:'Правка другой вкладки'};
    await saveReq.click();await requisites.getByRole('alert').filter({hasText:'Реквизиты изменились в другой вкладке'}).waitFor();
    assert.equal(reqWrites.length,3);assert.equal(reqWrites[2].expected_version,2);
    assert.equal(await recipient.inputValue(),'Несохранённый черновик');assert.equal(await saveReq.isDisabled(),true);
    await toggleReq.click();await toggleReq.click();assert.equal(reqReads.length,2);
    await requisites.getByText('Загрузить актуальные реквизиты',{exact:true}).click();
    const reloadReq=requisites.getByRole('button',{name:'Заменить черновик актуальной версией',exact:true});
    state.failReqRead=true;await reloadReq.click();
    await requisites.getByRole('alert').filter({hasText:'Не удалось загрузить актуальные реквизиты'}).waitFor();
    assert.equal(await recipient.inputValue(),'Несохранённый черновик');assert.equal(await saveReq.isDisabled(),true);
    state.failReqRead=false;await reloadReq.click();
    await until(async()=>await recipient.inputValue()==='Правка другой вкладки','Latest bank version missing');
    await recipient.fill('Правка после обновления');await saveReq.click();
    await requisites.getByRole('status').filter({hasText:'Реквизиты сохранены'}).waitFor();
    assert.equal(reqWrites.length,4);assert.equal(reqWrites[3].expected_version,3);assert.equal(bankRecord.version,4);
    for(const width of [320,390,736,1280]){
        await page.setViewportSize({width,height:850});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Open bank form overflows at ${width}`);
    }
    if(process.env.GB_ADMIN_PROOF_DIR)await requisites.screenshot({path:path.join(process.env.GB_ADMIN_PROOF_DIR,'owner-requisites.png'),animations:'disabled'});
    await toggleReq.click();
    // A confirmed payout stays confirmed if its subsequent dashboard read fails.
    state.failDashboardAfterPayout=true;
    await finance.getByRole('button',{name:'Вывести деньги',exact:true}).click();
    await finance.getByRole('spinbutton',{name:'Сумма выплаты',exact:true}).fill('5');
    await finance.getByRole('button',{name:'Подтвердить вывод',exact:true}).click();
    await page.getByRole('status').filter({hasText:'Заявка на выплату отправлена'}).waitFor();
    await page.getByRole('alert').filter({hasText:'Не удалось обновить сводку'}).waitFor();
    assert.equal(payoutWrites.length,1);assert.equal(await finance.getByRole('button',{name:'Вывести деньги',exact:true}).isDisabled(),true);
    state.failDashboardRead=false;await page.getByRole('button',{name:'Обновить сводку',exact:true}).click();
    await until(async()=>(await finance.innerText()).includes('95,00'),'Latest balance missing');
    assert.equal(payoutWrites.length,1);
    const communities=page.getByRole('region',{name:'Мои сообщества',exact:true});
    const ownCards=communities.getByRole('article');
    await until(async()=>await ownCards.count()===24,'Owner summary page missing');
    assert.equal(ownerDetailReads.length,0,'List cards must not request complete landing details');
    state.invalidOwnerCursor=true;await communities.getByRole('button',{name:'Ещё сообщества',exact:true}).click();
    await communities.getByRole('alert').filter({hasText:'Список изменился'}).waitFor();
    assert.equal(await ownCards.count(),24);assert.equal(await communities.getByRole('button',{name:'Ещё сообщества',exact:true}).count(),0);
    state.invalidOwnerCursor=false;await communities.getByRole('button',{name:'Повторить',exact:true}).click();
    state.failOwnerAppend=true;await communities.getByRole('button',{name:'Ещё сообщества',exact:true}).click();
    await communities.getByRole('alert').waitFor();assert.equal(await ownCards.count(),24);
    state.failOwnerAppend=false;await communities.getByRole('button',{name:'Ещё сообщества',exact:true}).click();
    await until(async()=>await ownCards.count()===48,'Owner list continuation recovery missing');
    while(await communities.getByRole('button',{name:'Ещё сообщества',exact:true}).count()){
        const before=await ownCards.count();await communities.getByRole('button',{name:'Ещё сообщества',exact:true}).click();await until(async()=>await ownCards.count()>before,'Owner list continuation missing');
    }
    assert.equal(await ownCards.count(),130);assert.equal(ownerDetailReads.length,0);
    const ownCard=ownCards.filter({has:page.getByText('Коллекция автора',{exact:true})});
    state.failOwnerDetail=true;await ownCard.getByRole('button',{name:'Редактировать',exact:true}).click();
    await communities.getByRole('alert').waitFor();assert.equal(await page.getByRole('form',{name:'Редактор сообщества',exact:true}).count(),0);
    state.failOwnerDetail=false;
    const privateReadsBeforeOwner=reads.length;
    await ownCard.getByRole('button',{name:'Редактировать',exact:true}).click();
    const ownerForm=page.getByRole('form',{name:'Редактор сообщества',exact:true});
    const ownerPicker=ownerForm.locator('fieldset').filter({has:page.getByRole('searchbox',{name:'Найти модель в каталоге',exact:true})}).last();
    const ownerChosen=ownerPicker.getByRole('list',{name:'Модели коллекции',exact:true});
    await ownerPicker.getByRole('alert').filter({hasText:'Названия выбранных моделей недоступны'}).waitFor();
    assert.equal(await ownerChosen.locator('li').count(),2);
    state.failSelected=false;await ownerPicker.getByRole('alert').getByRole('button',{name:'Повторить',exact:true}).click();
    await ownerChosen.getByText('Сейчас недоступна в каталоге. Удалите её перед публикацией.',{exact:true}).waitFor();
    assert.equal(await ownerChosen.locator('li').count(),2);
    assert.equal(await ownerPicker.getByRole('checkbox',{name:/Модель 125/}).count(),0,'Owner must not receive hidden admin products');
    state.invalidCursor=true;await ownerPicker.getByRole('button',{name:'Ещё модели',exact:true}).click();
    await ownerPicker.getByRole('alert').filter({hasText:'Список изменился'}).waitFor();
    assert.equal(await ownerPicker.getByRole('button',{name:'Ещё модели',exact:true}).count(),0);
    state.invalidCursor=false;await ownerPicker.getByRole('alert').getByRole('button',{name:'Повторить',exact:true}).click();
    await ownerPicker.getByRole('searchbox',{name:'Найти модель в каталоге',exact:true}).fill('Модель 001');
    await ownerPicker.getByRole('checkbox',{name:/^Модель 001/}).check();
    await ownerPicker.getByRole('button',{name:'Поднять модель 1',exact:true}).click();
    await ownerPicker.getByRole('button',{name:'Убрать модель 999',exact:true}).click();
    for(const width of [320,390,736]){await page.setViewportSize({width,height:850});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Owner picker overflows at ${width}`)}
    if(process.env.GB_ADMIN_PROOF_DIR)await ownerPicker.screenshot({path:path.join(process.env.GB_ADMIN_PROOF_DIR,'owner-product-picker.png')});
    await ownerForm.getByRole('button',{name:'Сохранить изменения',exact:true}).click();
    await until(()=>ownerWrites.length===1,'Owner picker order was not saved');
    assert.deepEqual(ownerWrites[0].product_ids,[130,1]);
    assert.ok(publicReads.every(read=>read.auth===null));
    assert.equal(reads.length,privateReadsBeforeOwner,'Owner picker must use only public catalog reads');
    await page.goto(base+'/production');await page.getByRole('navigation',{name:'Разделы администратора'}).waitFor();
    await page.getByRole('button',{name:'Модели и склад',exact:true}).click();
    const modelCards=page.locator('article').filter({has:page.locator('h4')});
    await until(async()=>await modelCards.count()===24,'Reference model page missing');
    assert.equal(modelDetailReads.length,0,'Reference list must not prefetch full model sizes');
    await page.getByText('130 моделей · активна',{exact:true}).waitFor();
    state.failReferenceAppend=true;await page.getByRole('button',{name:'Ещё модели изделий',exact:true}).click();await page.getByRole('alert').filter({hasText:'Reference append failed'}).waitFor();assert.equal(await modelCards.count(),24);
    state.failReferenceAppend=false;await page.getByRole('button',{name:'Ещё модели изделий',exact:true}).click();
    await until(async()=>await modelCards.count()===48,'Reference model append did not recover');
    while(await page.getByRole('button',{name:'Ещё модели изделий',exact:true}).count()){
        const before=await modelCards.count();await page.getByRole('button',{name:'Ещё модели изделий',exact:true}).click();await until(async()=>await modelCards.count()>before,'Reference model continuation missing');
    }
    assert.equal(await modelCards.count(),130);
    state.failModelRead=true;await page.getByRole('button',{name:'Изменить модель Модель 130',exact:true}).click();
    const modelDialog=page.getByRole('dialog',{name:'Изменить модель',exact:true});await modelDialog.getByRole('alert').waitFor();assert.equal(await modelDialog.locator('form').count(),0);
    state.failModelRead=false;await modelDialog.getByRole('button',{name:'Повторить загрузку модели',exact:true}).click();
    await modelDialog.getByLabel('Название',{exact:true}).fill('Модель 130 изменено');
    assert.equal(await modelDialog.getByLabel('Базовая ширина, см',{exact:true}).inputValue(),'64.25');
    assert.equal(await modelDialog.getByLabel('Базовая длина, см',{exact:true}).inputValue(),'72.35');
    for(const [width,height] of [[320,850],[390,850],[736,390],[1280,850]]){
        await page.setViewportSize({width,height});
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Model editor page overflows at ${width}`);
        assert.ok(await modelDialog.locator('form').evaluate(form=>form.parentElement.scrollWidth<=form.parentElement.clientWidth+1),`Model editor form overflows at ${width}`);
    }
    if(process.env.GB_ADMIN_PROOF_DIR)await modelDialog.screenshot({path:path.join(process.env.GB_ADMIN_PROOF_DIR,'model-geometry-dialog.png'),animations:'disabled'});
    assert.deepEqual(await modelDialog.locator('form').evaluate(form=>[...form.elements].filter(el=>el.willValidate&&!el.validity.valid).map(el=>({label:el.closest('label')?.textContent,value:el.value,message:el.validationMessage}))),[],'Model form should be valid before save');
    state.failModelSave=true;await modelDialog.getByRole('button',{name:'Сохранить модель',exact:true}).click();
    await modelDialog.getByText('Тестовый отказ сохранения модели',{exact:true}).waitFor();assert.equal(await modelDialog.getByLabel('Название',{exact:true}).inputValue(),'Модель 130 изменено');
    state.failModelSave=false;await modelDialog.getByRole('button',{name:'Сохранить модель',exact:true}).click();
    await until(()=>modelEdits.length===2,'Reference model save missing');
    assert.equal(modelEdits[1].sizes.length,1,'Archived size must not be reactivated');assert.equal(modelEdits[1].sizes[0].base_width_cm,'64.25');assert.equal(modelEdits[1].sizes[0].base_length_cm,'72.35');assert.equal(modelEdits[1].sizes[0].extra_width_price_per_cm,'3.25');
    await modelDialog.waitFor({state:'detached'});
    const modelOperationProof=await checkModelOperationFlow(page,{fixture:modelEditorFixture,modelRecord,referenceModels,png});
    const modelSearch=page.getByRole('textbox',{name:'Поиск модели',exact:true});state.delayReferenceSearch=true;await modelSearch.fill('Модель 00');await until(()=>heldReferenceSearch.length===1,'Slow reference search missing');
    await modelSearch.fill('Модель 130');await until(async()=>await modelCards.count()===1,'New reference search missing');state.delayReferenceSearch=false;heldReferenceSearch.splice(0).forEach(send=>send());assert.equal(await modelCards.count(),1);
    await page.getByRole('button',{name:'Ткани',exact:true}).click();
    const fabricRows=page.locator('tbody tr');await until(async()=>await fabricRows.count()===24,'Fabric page missing');
    assert.ok((await fabricRows.nth(1).innerText()).includes('25 м'),'Fabric available meters were replaced by zero');
    state.invalidReferenceCursor=true;await page.getByRole('button',{name:'Ещё ткани',exact:true}).click();await page.getByRole('alert').filter({hasText:'Список изменился'}).waitFor();assert.equal(await fabricRows.count(),24);
    state.invalidReferenceCursor=false;await page.getByRole('button',{name:'Обновить список тканей',exact:true}).click();
    await page.getByRole('button',{name:'Ещё ткани',exact:true}).waitFor();
    while(await page.getByRole('button',{name:'Ещё ткани',exact:true}).count()){
        const before=await fabricRows.count();await page.getByRole('button',{name:'Ещё ткани',exact:true}).click();await until(async()=>await fabricRows.count()>before,'Fabric continuation missing');
    }
    assert.equal(await fabricRows.count(),130);const targetFabric=fabricRows.filter({hasText:'Ткань 130'});
    await targetFabric.getByRole('button',{name:'Изменить',exact:true}).click();
    const fabricDialog=page.getByRole('dialog',{name:'Изменить ткань',exact:true});await fabricDialog.getByLabel('Название',{exact:true}).fill('Ткань 130 изменено');
    await fabricDialog.getByRole('button',{name:'Сохранить',exact:true}).click();await until(()=>fabricEdits.length===1,'Fabric save missing');assert.equal(fabricEdits[0].cost_per_meter,12.34);assert.equal(fabricEdits[0].balance,undefined);assert.equal(fabricEdits[0].minimum_stock_meters,15.123);
    await fabricDialog.waitFor({state:'detached'});
    const expense=page.locator('section').filter({has:page.getByRole('heading',{name:'Расход ткани по моделям',exact:true})}).last();
    const expenseCards=expense.locator('button').filter({has:page.locator('strong')});
    await until(async()=>await expenseCards.count()===24,'Requirement page missing');
    while(await page.getByRole('button',{name:'Ещё расходы ткани',exact:true}).count()){
        const before=await expenseCards.count();await page.getByRole('button',{name:'Ещё расходы ткани',exact:true}).click();await until(async()=>await expenseCards.count()>before,'Requirement continuation missing');
    }
    assert.equal(await expenseCards.count(),130);await expenseCards.filter({hasText:'Модель 130'}).click();
    const requirementDialog=page.getByRole('dialog',{name:'Расход ткани',exact:true});
    await until(async()=>await requirementDialog.getByRole('combobox',{name:'Модель',exact:true}).inputValue()==='130','Existing expense model selection missing');
    await requirementDialog.getByRole('searchbox',{name:'Поиск модели для расхода',exact:true}).fill('не найдено');
    await requirementDialog.getByRole('searchbox',{name:'Поиск ткани для расхода',exact:true}).fill('не найдено');
    await until(async()=>await requirementDialog.getByRole('option',{name:'Модель 001',exact:true}).count()===0,'Picker search did not finish');
    assert.equal(await requirementDialog.getByRole('combobox',{name:'Модель',exact:true}).inputValue(),'130');assert.equal(await requirementDialog.getByRole('combobox',{name:'Ткань',exact:true}).inputValue(),'130');
    await until(async()=>await requirementDialog.getByRole('status').filter({hasText:'По этому запросу ничего не найдено.'}).count()===2,'Both picker searches must finish without losing their selection');
    for(const [width,height] of [[320,850],[390,850],[736,390],[1280,850]]){
        await page.setViewportSize({width,height});
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Reference picker page overflows at ${width}`);
        assert.ok(await requirementDialog.locator('form').evaluate(form=>form.parentElement.scrollWidth<=form.parentElement.clientWidth+1),`Reference picker form overflows at ${width}`);
    }
    if(process.env.GB_ADMIN_PROOF_DIR)await requirementDialog.screenshot({path:path.join(process.env.GB_ADMIN_PROOF_DIR,'fabric-requirement-dialog.png'),animations:'disabled'});
    await requirementDialog.getByRole('button',{name:'Сохранить расход',exact:true}).click();await until(()=>requirementEdits.length===1,'Expense save missing');assert.equal(requirementEdits[0].meters_per_unit,1.234);assert.equal(requirementEdits[0].garment_model_id,130);assert.equal(requirementEdits[0].fabric_id,130);
    await requirementDialog.waitFor({state:'detached'});
    for(const width of [320,390,736,1280]){await page.setViewportSize({width,height:850});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Reference directory overflows at ${width}`)}
    assert.ok(referenceReads.length>15);assert.ok(referenceReads.every(row=>row.limit==='24'));
    // Stock pages and independently selected references extend past the former 100-row limit.
    const oldModelReads=optionReads.filter(row=>row.path==='/api/production/admin/assortment/models').length;
    await page.getByRole('button',{name:'Фурнитура',exact:true}).click();
    const accessoryCards=page.locator('article').filter({has:page.locator('h4')});
    const categoryButtons=page.locator('[aria-label="Категории фурнитуры"] button');
    const accessoryRelations=page.locator('section').filter({has:page.getByRole('heading',{name:'Применимость и расход',exact:true})}).last();
    const accessoryRelationCards=accessoryRelations.locator('button').filter({has:page.locator('strong')});
    async function allStockPages(label,rows){
        await until(async()=>await rows.count()===24,`${label}: first page missing`);
        while(await page.getByRole('button',{name:label,exact:true}).count()){
            const before=await rows.count();await page.getByRole('button',{name:label,exact:true}).click();
            await until(async()=>await rows.count()>before,`${label}: continuation missing`);
        }
        assert.equal(await rows.count(),130,`${label}: rows after 100 must be reachable`);
    }
    await until(async()=>await accessoryCards.count()===24,'Accessory first page missing');
    await accessoryCards.first().getByText('Подходит для 130 моделей',{exact:true}).waitFor();
    state.failStockAppend=true;await page.getByRole('button',{name:'Ещё фурнитура',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'Тестовый отказ страницы склада'}).waitFor();assert.equal(await accessoryCards.count(),24);
    state.failStockAppend=false;
    await allStockPages('Ещё фурнитура',accessoryCards);
    await allStockPages('Ещё категории',categoryButtons);
    await allStockPages('Ещё расход фурнитуры',accessoryRelationCards);
    await page.getByRole('button',{name:'Фильтры',exact:true}).click();
    const stockFilter=page.getByRole('dialog',{name:'Фильтры',exact:true});
    await stockFilter.getByRole('radio',{name:'Категория фурнитуры 130',exact:true}).check();
    await stockFilter.getByRole('button',{name:'Показать',exact:true}).click();
    await until(async()=>await accessoryCards.count()===1,'Accessory category filter missing');
    const categorySearch=page.getByRole('searchbox',{name:'Найти категорию фурнитуры',exact:true});
    await categorySearch.fill('не найдено');await until(async()=>await categoryButtons.count()===0,'Category search missing');
    await page.getByRole('button',{name:/^Фильтры/}).click();
    assert.equal(await stockFilter.getByRole('radio',{name:'Категория фурнитуры 130',exact:true}).isChecked(),true,'Chosen category must survive unrelated category search');
    await stockFilter.getByRole('button',{name:'Закрыть фильтры',exact:true}).click();
    await categorySearch.fill('Категория фурнитуры 130');await categoryButtons.filter({hasText:/^Категория фурнитуры 130$/}).click();
    const categoryDialog=page.getByRole('dialog',{name:'Изменить категорию',exact:true});
    assert.equal(await categoryDialog.getByRole('textbox',{name:/^Описание/}).inputValue(),'Описание категории 130');
    await categoryDialog.getByLabel('Название',{exact:true}).fill('Категория 130 изменено');
    await categoryDialog.getByRole('button',{name:'Сохранить',exact:true}).click();await categoryDialog.waitFor({state:'detached'});
    assert.equal(stockWrites.find(row=>row.kind==='accessory-categories').payload.description,'Описание категории 130');
    await page.getByRole('button',{name:/^Фильтры/}).click();
    assert.equal(await stockFilter.getByRole('radio',{name:'Категория 130 изменено',exact:true}).isChecked(),true);
    await stockFilter.getByRole('button',{name:'Закрыть фильтры',exact:true}).click();
    await page.getByRole('button',{name:'Изменить Фурнитура 130',exact:true}).click();
    const accessoryDialog=page.getByRole('dialog',{name:'Изменить фурнитуру',exact:true});
    await until(async()=>await accessoryDialog.getByRole('combobox',{name:'Категория',exact:true}).inputValue()==='130','Selected category 130 missing');
    await accessoryDialog.getByRole('searchbox',{name:'Поиск категории фурнитуры',exact:true}).fill('не найдено');
    await accessoryDialog.getByRole('status').filter({hasText:'По этому запросу ничего не найдено.'}).waitFor();
    assert.equal(await accessoryDialog.getByRole('combobox',{name:'Категория',exact:true}).inputValue(),'130');
    await accessoryDialog.getByLabel('Название',{exact:true}).fill('Фурнитура 130 изменено');
    state.delayStockSave=true;state.failStockSave=true;await accessoryDialog.getByRole('button',{name:'Сохранить',exact:true}).click();
    await until(()=>heldStockSaves.length===1,'Accessory save was not held');
    assert.equal(await accessoryDialog.getByLabel('Название',{exact:true}).isDisabled(),true);
    assert.equal(await accessoryDialog.getByRole('button',{name:'Закрыть',exact:true}).isDisabled(),true);
    assert.equal(await page.getByRole('button',{name:'Добавить фурнитуру',exact:true}).isDisabled(),true);
    state.delayStockSave=false;heldStockSaves.splice(0).forEach(send=>send());
    await accessoryDialog.getByText('Тестовый отказ сохранения склада',{exact:true}).waitFor();
    assert.equal(await accessoryDialog.getByLabel('Название',{exact:true}).inputValue(),'Фурнитура 130 изменено');
    state.failStockSave=false;
    for(const [width,height] of [[320,850],[390,850],[736,390],[1280,850]]){
        await page.setViewportSize({width,height});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Accessory editor overflows at ${width}`);
        assert.ok(await accessoryDialog.locator('form').evaluate(form=>form.parentElement.scrollWidth<=form.parentElement.clientWidth+1),`Accessory form overflows at ${width}`);
    }
    if(process.env.GB_ADMIN_PROOF_DIR)await accessoryDialog.screenshot({path:path.join(process.env.GB_ADMIN_PROOF_DIR,'accessory-editor.png'),animations:'disabled'});
    await accessoryDialog.getByRole('button',{name:'Сохранить',exact:true}).click();await accessoryDialog.waitFor({state:'detached'});
    const accessorySaves=stockWrites.filter(row=>row.kind==='accessories');assert.equal(accessorySaves.length,2);assert.deepEqual(accessorySaves[0].payload,accessorySaves[1].payload);assert.equal(accessorySaves[1].payload.unit_cost,12.34);assert.equal(accessorySaves[1].payload.stock_quantity,25);assert.equal(accessorySaves[1].payload.category_id,130);
    await accessoryRelationCards.filter({hasText:modelRecord(130).name}).click();
    const accessoryExpenseDialog=page.getByRole('dialog',{name:'Применимость фурнитуры',exact:true});
    for(const name of ['Поиск модели для расхода','Поиск фурнитуры для расхода'])await accessoryExpenseDialog.getByRole('searchbox',{name,exact:true}).fill('не найдено');
    await until(async()=>await accessoryExpenseDialog.getByRole('status').filter({hasText:'По этому запросу ничего не найдено.'}).count()===2,'Accessory requirement selection searches missing');
    assert.equal(await accessoryExpenseDialog.getByRole('combobox',{name:'Модель',exact:true}).inputValue(),'130');assert.equal(await accessoryExpenseDialog.getByRole('combobox',{name:'Фурнитура',exact:true}).inputValue(),'130');
    await accessoryExpenseDialog.getByRole('button',{name:'Сохранить',exact:true}).click();await accessoryExpenseDialog.waitFor({state:'detached'});
    const accessoryExpenseSave=stockWrites.find(row=>row.kind==='accessory-requirements').payload;
    assert.equal(accessoryExpenseSave.quantity_per_unit,1.234);assert.equal(accessoryExpenseSave.is_optional,true);assert.equal(accessoryExpenseSave.notes,'Комментарий 130');
    await page.getByRole('button',{name:'Коробки',exact:true}).click();
    const boxCards=page.locator('article').filter({has:page.locator('h4')});
    const packagingRelations=page.locator('section').filter({has:page.getByRole('heading',{name:'Правила упаковки',exact:true})}).last();
    const packagingCards=packagingRelations.locator('button').filter({has:page.locator('strong')});
    await until(async()=>await boxCards.count()===24,'Box first page missing');
    state.invalidStockCursor=true;await page.getByRole('button',{name:'Ещё коробки',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'Список изменился'}).waitFor();assert.equal(await boxCards.count(),24);
    state.invalidStockCursor=false;await page.getByRole('button',{name:'Обновить коробки',exact:true}).click();
    await allStockPages('Ещё коробки',boxCards);await allStockPages('Ещё правила упаковки',packagingCards);
    await page.getByRole('button',{name:'Изменить коробку Коробка 130',exact:true}).click();
    const boxDialog=page.getByRole('dialog',{name:'Изменить коробку',exact:true});
    await boxDialog.getByLabel('Название',{exact:true}).fill('Коробка 130 изменено');
    await boxDialog.getByRole('button',{name:'Сохранить',exact:true}).click();await boxDialog.waitFor({state:'detached'});
    const boxSave=stockWrites.find(row=>row.kind==='boxes').payload;
    assert.equal(boxSave.inner_length_cm,30.25);assert.equal(boxSave.inner_width_cm,20.35);assert.equal(boxSave.inner_height_cm,10.45);assert.equal(boxSave.unit_cost,12.34);assert.equal(boxSave.stock_quantity,25);assert.equal(boxSave.max_items,7);
    await packagingCards.filter({hasText:modelRecord(130).name}).click();
    const packagingDialog=page.getByRole('dialog',{name:'Правило упаковки',exact:true});
    const maximum=packagingDialog.getByLabel('Максимум изделий этой модели',{exact:true});
    assert.equal(await maximum.inputValue(),'3');assert.equal(await maximum.getAttribute('max'),'7');
    assert.equal(await packagingDialog.getByRole('combobox',{name:'Коробка',exact:true}).inputValue(),'130');
    await packagingDialog.getByRole('searchbox',{name:'Поиск коробки',exact:true}).fill('Коробка 129');
    await until(async()=>await packagingDialog.getByRole('option',{name:'Коробка 129 · до 2 шт.',exact:true}).count()===1,'Box beyond first page missing');
    await packagingDialog.getByRole('combobox',{name:'Коробка',exact:true}).selectOption('129');
    assert.equal(await maximum.inputValue(),'2');assert.equal(await maximum.getAttribute('max'),'2');
    await packagingDialog.getByRole('searchbox',{name:'Поиск коробки',exact:true}).fill('не найдено');
    await packagingDialog.getByRole('searchbox',{name:'Поиск модели для расхода',exact:true}).fill('не найдено');
    await until(async()=>await packagingDialog.getByRole('status').filter({hasText:'По этому запросу ничего не найдено.'}).count()===2,'Packaging selection searches missing');
    assert.equal(await packagingDialog.getByRole('combobox',{name:'Коробка',exact:true}).inputValue(),'129');assert.equal(await packagingDialog.getByRole('combobox',{name:'Модель',exact:true}).inputValue(),'130');
    for(const [width,height] of [[320,850],[390,850],[736,390],[1280,850]]){
        await page.setViewportSize({width,height});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Packaging editor overflows at ${width}`);
        assert.ok(await packagingDialog.locator('form').evaluate(form=>form.parentElement.scrollWidth<=form.parentElement.clientWidth+1),`Packaging form overflows at ${width}`);
    }
    if(process.env.GB_ADMIN_PROOF_DIR)await packagingDialog.screenshot({path:path.join(process.env.GB_ADMIN_PROOF_DIR,'packaging-rule.png'),animations:'disabled'});
    await packagingDialog.getByRole('button',{name:'Сохранить правило',exact:true}).click();await packagingDialog.waitFor({state:'detached'});
    const packagingSave=stockWrites.find(row=>row.kind==='packaging-rules').payload;
    assert.equal(packagingSave.box_id,129);assert.equal(packagingSave.garment_model_id,130);assert.equal(packagingSave.max_items,2);
    assert.ok(stockReads.every(row=>row.limit==='24'));assert.equal(optionReads.filter(row=>row.path==='/api/production/admin/assortment/models').length,oldModelReads,'Stock views must not load legacy first-100 models');
    await page.getByRole('button',{name:'Техкарты',exact:true}).click();
    const techCards=page.locator('article').filter({has:page.locator('h4')});
    const techSearch=page.getByRole('searchbox',{name:'Поиск техкарты',exact:true});
    await until(async()=>await techCards.count()===24,'Tech-card summary page missing');
    assert.equal(techSources.length,0,'Listing cards must not prefetch any revision source');
    state.failTechAppend=true;await page.getByRole('button',{name:'Ещё техкарты',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'Тестовый отказ страницы техкарт'}).waitFor();assert.equal(await techCards.count(),24);
    state.failTechAppend=false;await page.getByRole('button',{name:'Ещё техкарты',exact:true}).click();
    await until(async()=>await techCards.count()===48,'Tech-card continuation retry missing');
    state.invalidTechCursor=true;await page.getByRole('button',{name:'Ещё техкарты',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'Список изменился'}).waitFor();assert.equal(await techCards.count(),48);
    state.invalidTechCursor=false;await page.getByRole('button',{name:'Обновить техкарты',exact:true}).click();
    await allStockPages('Ещё техкарты',techCards);
    const draft128=techCards.filter({has:page.getByRole('heading',{name:'Модель 128',exact:true})});
    assert.equal(await draft128.getByRole('button',{name:'Новая версия',exact:true}).count(),0);
    assert.equal(await draft128.getByRole('button',{name:'Черновик уже есть',exact:true}).isDisabled(),true);
    state.delayTechSource=true;await techCards.filter({has:page.getByRole('heading',{name:'Модель 129',exact:true})}).getByRole('button',{name:'Новая версия',exact:true}).click();
    await until(()=>heldTechSources.length===1,'Revision source read was not held');
    await page.getByRole('dialog',{name:'Новая версия техкарты',exact:true}).getByRole('button',{name:'Закрыть',exact:true}).click();
    state.delayTechSource=false;heldTechSources.splice(0).forEach(send=>send());
    assert.equal(await page.getByRole('dialog').count(),0,'Closed source read must not reopen its editor');
    state.delayTechSearch=true;await techSearch.fill('Модель 00');await until(()=>heldTechSearch.length===1,'Slow tech-card search missing');
    await techSearch.fill('Модель 130');await until(async()=>await techCards.count()===1,'New tech-card search missing');
    state.delayTechSearch=false;heldTechSearch.splice(0).forEach(send=>send());assert.equal(await techCards.count(),1);
    state.failTechSource=true;await techCards.getByRole('button',{name:'Новая версия',exact:true}).click();
    const techDialog=page.getByRole('dialog',{name:'Новая версия техкарты',exact:true});
    await techDialog.getByRole('alert').filter({hasText:'Тестовый отказ исходной версии'}).waitFor();assert.equal(await techDialog.locator('form').count(),0);
    state.failTechSource=false;state.incompleteTechSource=true;await techDialog.getByRole('button',{name:'Повторить загрузку техкарты',exact:true}).click();
    await techDialog.getByRole('alert').filter({hasText:'Сервер вернул неполную операцию'}).waitFor();assert.equal(await techDialog.locator('form').count(),0);
    state.incompleteTechSource=false;state.techSourceConflict=true;await techDialog.getByRole('button',{name:'Повторить загрузку техкарты',exact:true}).click();
    await techDialog.getByRole('alert').filter({hasText:'У техкарты уже есть черновик'}).waitFor();assert.equal(await techDialog.locator('form').count(),0);
    state.techSourceConflict=false;await techDialog.getByRole('button',{name:'Повторить загрузку техкарты',exact:true}).click();
    await techDialog.getByLabel('Название версии',{exact:true}).fill('Моя рабочая версия');
    assert.equal(await techDialog.getByRole('combobox',{name:'Участок',exact:true}).first().inputValue(),'sewing');
    assert.equal(await techDialog.getByRole('combobox',{name:'Участок',exact:true}).first().getByRole('option',{name:'Цех · сохранённое назначение',exact:true}).count(),1);
    assert.equal(await techDialog.getByRole('combobox',{name:'Роль исполнителя',exact:true}).first().inputValue(),'qc');
    assert.equal(await techDialog.getByLabel('Норма времени, мин',{exact:true}).first().inputValue(),'12.34');
    assert.equal(await techDialog.getByLabel('Стоимость работы',{exact:true}).first().inputValue(),'3.25');
    state.failTechSave=true;state.delayTechSave=true;await techDialog.getByRole('button',{name:'Сохранить черновик',exact:true}).click();
    await until(()=>heldTechSaves.length===1,'Tech-card save was not held');
    assert.equal(await techDialog.getByLabel('Название версии',{exact:true}).isDisabled(),true);
    assert.equal(await techDialog.getByRole('button',{name:'Закрыть',exact:true}).isDisabled(),true);
    assert.equal(await page.getByRole('button',{name:'Создать техкарту',exact:true}).isDisabled(),true);
    state.delayTechSave=false;heldTechSaves.splice(0).forEach(send=>send());
    await techDialog.getByText('Тестовый отказ сохранения техкарты',{exact:true}).waitFor();
    assert.equal(await techDialog.getByLabel('Название версии',{exact:true}).inputValue(),'Моя рабочая версия');state.failTechSave=false;
    for(const [width,height] of [[320,850],[390,850],[736,390],[1280,850]]){
        await page.setViewportSize({width,height});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Tech-card editor overflows at ${width}`);
        assert.ok(await techDialog.locator('form').evaluate(form=>form.parentElement.scrollWidth<=form.parentElement.clientWidth+1),`Tech-card form overflows at ${width}`);
    }
    if(process.env.GB_ADMIN_PROOF_DIR)await techDialog.screenshot({path:path.join(process.env.GB_ADMIN_PROOF_DIR,'tech-card-editor.png'),animations:'disabled'});
    await techDialog.getByRole('button',{name:'Сохранить черновик',exact:true}).click();await techDialog.waitFor({state:'detached'});
    assert.equal(techWrites.length,2);assert.deepEqual(techWrites[0].payload,techWrites[1].payload);assert.equal(techWrites[1].payload.expected_latest_revision,130);
    assert.equal(techWrites[1].payload.revision.checkpoints[0].stage_code,'sewing');assert.equal(techWrites[1].payload.revision.checkpoints[0].role_code,'qc');assert.equal(techWrites[1].payload.revision.checkpoints[0].standard_minutes,12.34);assert.equal(techWrites[1].payload.revision.checkpoints[0].labor_cost,3.25);
    await techCards.getByText('Версия 131',{exact:true}).waitFor();
    state.failTechPublish=true;await techCards.getByRole('button',{name:'Опубликовать',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'Тестовый отказ публикации'}).waitFor();assert.equal(techPublishes.length,1);
    state.failTechPublish=false;state.failTechRead=true;await techCards.getByRole('button',{name:'Опубликовать',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'Тестовый отказ списка техкарт'}).waitFor();assert.equal(techPublishes.length,2,'Confirmed publication must not repeat because a refresh failed');
    state.failTechRead=false;await page.getByRole('button',{name:'Обновить техкарты',exact:true}).click();
    await techCards.getByText('Черновика нет',{exact:false}).waitFor();assert.equal(techPublishes.length,2);
    await techSearch.fill('Модель 129');await until(async()=>await techCards.count()===1&&await techCards.getByRole('heading',{name:'Модель 129',exact:true}).count()===1,'Model 129 card missing');
    state.longTechSource=true;await techCards.getByRole('button',{name:'Новая версия',exact:true}).click();
    await until(async()=>await techDialog.getByRole('combobox',{name:'Участок',exact:true}).count()===200,'Full supported operation count missing');
    assert.equal(await techDialog.getByRole('button',{name:'Добавить операцию',exact:true}).isDisabled(),true);
    await techDialog.getByRole('button',{name:'Закрыть',exact:true}).click();state.longTechSource=false;
    await techSearch.fill('не найдено');await until(async()=>await techCards.count()===0,'Empty tech-card result missing');
    await page.getByRole('button',{name:'Создать техкарту',exact:true}).click();
    const newTechDialog=page.getByRole('dialog',{name:'Новая техкарта',exact:true});
    const freeSelect=newTechDialog.getByRole('combobox',{name:'Модель',exact:true});
    assert.equal(await freeSelect.inputValue(),'','New cards must require an explicit model choice');
    await until(async()=>await freeSelect.getByRole('option').count()===25,'Available model first page missing');
    while(await newTechDialog.getByRole('button',{name:'Ещё модели без техкарты',exact:true}).count()){
        const before=await freeSelect.getByRole('option').count();await newTechDialog.getByRole('button',{name:'Ещё модели без техкарты',exact:true}).click();await until(async()=>await freeSelect.getByRole('option').count()>before,'Available model continuation missing');
    }
    assert.equal(await freeSelect.getByRole('option').count(),131);await freeSelect.selectOption('1130');
    await newTechDialog.getByRole('searchbox',{name:'Поиск модели без техкарты',exact:true}).fill('не найдено');
    await newTechDialog.getByRole('status').filter({hasText:'По этому запросу ничего не найдено.'}).waitFor();assert.equal(await freeSelect.inputValue(),'1130');
    await newTechDialog.getByLabel('Код карты',{exact:true}).fill('NEW-TECH');await newTechDialog.getByLabel('Название версии',{exact:true}).fill('Для новой модели');
    await newTechDialog.getByLabel('Операция',{exact:true}).fill('Новая операция');await newTechDialog.getByLabel('Норма времени, мин',{exact:true}).fill('12.34');await newTechDialog.getByLabel('Стоимость работы',{exact:true}).fill('3.25');
    for(const [width,height] of [[320,850],[390,850],[736,390],[1280,850]]){await page.setViewportSize({width,height});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`New tech-card form overflows at ${width}`)}
    if(process.env.GB_ADMIN_PROOF_DIR)await newTechDialog.screenshot({path:path.join(process.env.GB_ADMIN_PROOF_DIR,'tech-card-new.png'),animations:'disabled'});
    await newTechDialog.getByRole('button',{name:'Сохранить черновик',exact:true}).click();await newTechDialog.waitFor({state:'detached'});
    assert.equal(techWrites.at(-1).create,true);assert.equal(techWrites.at(-1).id,1130);assert.equal(techWrites.at(-1).payload.expected_latest_revision,undefined);
    assert.ok(techReads.every(row=>row.limit==='24'));assert.equal(optionReads.filter(row=>row.path==='/api/production/admin/assortment/models').length,oldModelReads,'Tech-card view must not use the legacy first-100 model list');
    const patternProof=await checkPatternFlow({page,until,fixture:patternFixture,proofDir:process.env.GB_ADMIN_PROOF_DIR});
    const categoryProof=await checkCategoryFlow({page,until,fixture:categoryFixture,proofDir:process.env.GB_ADMIN_PROOF_DIR});
    for(const [session,scope,text] of [[false,'system','Вход в терминал'],[true,'production','Управление пресетами доступно системному администратору.']]){
        state.productionSession=session;state.productionScope=scope;
        const isolated=await browser.newContext({serviceWorkers:'block'}),isolatedPage=await isolated.newPage();
        await isolated.addInitScript(()=>localStorage.setItem('cookieConsent','accepted'));
        isolatedPage.on('pageerror',error=>errors.push(error.message));
        await isolatedPage.goto(base+'/admin/products/1/edit');
        await isolatedPage.getByText(text,{exact:true}).waitFor();
        assert.equal(await isolatedPage.getByRole('dialog').count(),0);await isolated.close();
    }

    // The real browser lock and storage events coordinate two production tabs.
    state.productionSession=true;state.productionScope='system';
    const authContext=await browser.newContext({serviceWorkers:'block'});
    await authContext.addInitScript(()=>localStorage.setItem('cookieConsent','accepted'));
    const first=await authContext.newPage(),second=await authContext.newPage();
    for(const tab of [first,second])tab.on('pageerror',error=>errors.push(error.message));
    await first.goto(base+'/production?section=presets');
    await first.getByRole('button',{name:/Garment Buro Пресетов/}).waitFor();
    const beforeEpoch=await first.evaluate(()=>JSON.parse(localStorage.getItem('gb-production-session-lifetime')).epoch);
    await first.getByRole('button',{name:/Garment Buro Пресетов/}).click();
    await first.getByRole('button',{name:'Изменить пресет Модель 001',exact:true}).click();
    await first.getByRole('dialog').getByLabel('Название',{exact:true}).fill('Черновик прежнего входа');
    await second.goto(base+'/production?section=presets');
    await second.getByRole('navigation',{name:'Разделы администратора'}).waitFor();
    state.delayProductionLogout=true;const loginCount=productionLogins.length;
    await second.getByRole('button',{name:'Выйти',exact:true}).click();
    await until(()=>heldProductionLogout.length===1,'Production logout not held');
    for(const tab of [first,second])await tab.getByRole('heading',{name:'Вход в терминал',exact:true}).waitFor();
    assert.equal(await first.getByRole('dialog').count(),0,'Old draft remained after remote logout intent');
    await first.getByLabel('Личный код сотрудника',{exact:true}).fill('123456');
    await first.getByRole('button',{name:'Войти в терминал',exact:true}).click();
    await until(async()=>await first.getByRole('button',{name:'Проверяем код…',exact:true}).count()===1,'Login was not queued');
    assert.equal(productionLogins.length,loginCount,'New login must wait for old logout cookie response');
    state.delayProductionLogout=false;heldProductionLogout.splice(0).forEach(send=>send());
    for(const tab of [first,second])await tab.getByRole('navigation',{name:'Разделы администратора'}).waitFor();
    const afterEpoch=await first.evaluate(()=>JSON.parse(localStorage.getItem('gb-production-session-lifetime')).epoch);
    assert.notEqual(afterEpoch,beforeEpoch);assert.equal(productionLogins.length,loginCount+1);
    const productionCookie=(await authContext.cookies()).find(cookie=>cookie.name==='gb_production_session');
    assert.equal(productionCookie.httpOnly,true);assert.equal(productionCookie.path,'/api/production');assert.equal(productionCookie.sameSite,'Strict');
    await first.getByRole('button',{name:/Garment Buro Пресетов/}).click();
    await first.getByRole('button',{name:'Изменить пресет Модель 001',exact:true}).click();
    assert.notEqual(await first.getByRole('dialog').getByLabel('Название',{exact:true}).inputValue(),'Черновик прежнего входа');
    state.failProductionLogout=true;
    await second.getByRole('button',{name:'Выйти',exact:true}).click();
    await second.getByRole('alert').filter({hasText:'Сервер не подтвердил выход'}).waitFor();
    const authReads=productionAuthReads.length;
    await first.reload();await first.getByRole('heading',{name:'Вход в терминал',exact:true}).waitFor();
    assert.equal(productionAuthReads.length,authReads,'Reload must not reopen a locally closed session after failed logout');
    for(const width of [320,390,736,1280]){await first.setViewportSize({width,height:850});assert.ok(await first.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Production login overflows at ${width}`)}
    await authContext.close();state.failProductionLogout=false;
    // A pending startup response cannot resurrect either tab after real logout.
    state.productionSession=true;
    const staleContext=await browser.newContext({serviceWorkers:'block'});
    await staleContext.addInitScript(()=>localStorage.setItem('cookieConsent','accepted'));
    const live=await staleContext.newPage(),starting=await staleContext.newPage();
    for(const tab of [live,starting])tab.on('pageerror',error=>errors.push(error.message));
    await live.goto(base+'/production?section=presets');await live.getByRole('navigation',{name:'Разделы администратора'}).waitFor();
    state.delayProductionMe=true;await starting.goto(base+'/production?section=presets');
    await until(()=>heldProductionMe.length===1,'Production initialization was not held');
    const outCount=productionLogouts.length;await live.getByRole('button',{name:'Выйти',exact:true}).click();
    for(const tab of [live,starting])await tab.getByRole('heading',{name:'Вход в терминал',exact:true}).waitFor();
    assert.equal(productionLogouts.length,outCount,'Logout must wait for the earlier locked initialization');
    state.delayProductionMe=false;heldProductionMe.splice(0).forEach(send=>send());
    await until(()=>productionLogouts.length===outCount+1&&!state.productionSession,'Queued logout did not finish');
    for(const tab of [live,starting])assert.equal(await tab.getByRole('navigation',{name:'Разделы администратора'}).count(),0);
    await staleContext.close();

    state.customer=false;
    console.log(JSON.stringify(await checkStorefrontLayout({browser,base})));

    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({stockDirectories:{accessories:130,categories:130,boxes:130,requirements:130,packagingRules:130},stockAppendRecovery:true,stockCursorRecovery:true,stockDraftAndSingleFlight:true,stockDecimalsPreserved:true,stockSelectedReferencesPast100:true,stockSelectionAcrossEmptySearch:true,categoryFilterSurvivesSearch:true,packagingCapacityIndependentOfPage:true,noLegacyModelsForStock:true}));
    console.log(JSON.stringify({techCards130:true,noTechSourcePrefetch:true,techAppendAndCursorRecovery:true,techSearchRace:true,sourceFailureIncompleteAndConflict:true,closedSourceIgnored:true,techOperationCodesAndDecimalsPreserved:true,techSaveSingleFlight:true,techDraftSurvivesFailure:true,publicationConfirmedDespiteRefreshFailure:true,techOperationLimit200:true,availableModels130:true,newTechModelExplicitAndPast100:true,noLegacyModelsForTechCards:true}));
    console.log(JSON.stringify(patternProof));
    console.log(JSON.stringify(categoryProof));
    console.log(JSON.stringify({...presetOperationProof,...modelOperationProof}));
    console.log(JSON.stringify({nextStandalone:true,syntheticBackend:true,sqlVerifiedSeparately:true,
        widths:[320,390,736,1280],firstPage:24,fullList:33,appendRecovery:true,staleSearch:true,
        serverFilters:true,cursorRecovery:true,identityPicker:true,detailFailureAndRetry:true,currentDetailReferences:true,preservedRawStockAndMedia:true,modelsPast100:true,primaryProductionEditor:true,productionUpload:true,oldRouteRedirects:true,deleteRecovery:true,pickerPages130:true,pickerLimit50:true,pickerSelectionAcrossSearch:true,ownerPublicPolicy:true,ownerUnavailableSelection:true,ownerOrderSaved:true,partnerPages130:true,partnerSearchRace:true,selectedNewProfileSurvivesLateRead:true,payoutPages130:true,payoutCursorRecovery:true,partnerSelectorPages:true,payoutIndependentFailure:true,ownerSummaryPages130:true,noDetailPrefetch:true,lazyBankRead:true,bankFailureIsLocal:true,bankDraftSurvivesSaveFailure:true,bankSaveSingleFlight:true,bankVersionConflict:true,bankExplicitReload:true,productionCrossTabLogout:true,productionCookieOrder:true,productionSameUserEpoch:true,productionLateInitializeIgnored:true,productionFailedLogoutStaysClosed:true,referenceModels130:true,referenceFabrics130:true,referenceRequirements130:true,referenceScalarSummaries:true,referenceGeometryPreserved:true,referenceSelectedAcrossSearch:true,referenceNativeMeterBalance:true,payoutConfirmedDespiteRefreshFailure:true,physicalProduct:true,staleWriteAndPhysicalStock:true,draftSurvivesReloadFailure:true,phoneConflict:true,landingPagesBothSessions:true,landingSearchRace:true,noLandingPrefetch:true,compactMemberships:true,publicationFromSummary:true,requests:reads.length}));
} catch(error) {
    console.error('Browser gate failed:',error.message, currentPage?await currentPage.locator('body').innerText().then(text=>text.slice(-2500)).catch(()=>'<closed>'):'<no page>');
    throw error;
} finally {
    held.splice(0).forEach(send=>send());
    heldDirectory.splice(0).forEach(send=>send());
    heldProfiles.splice(0).forEach(send=>send());
    heldReqSaves.splice(0).forEach(send=>send());
    heldReferenceSearch.splice(0).forEach(send=>send());
    heldStockSaves.splice(0).forEach(send=>send());
    heldTechSources.splice(0).forEach(send=>send());
    heldTechSaves.splice(0).forEach(send=>send());
    heldTechSearch.splice(0).forEach(send=>send());
    modelEditorFixture.release();
    patternFixture.release();
    categoryFixture.release();
    heldProductionMe.splice(0).forEach(send=>send());
    heldProductionLogout.splice(0).forEach(send=>send());
    await browser?.close();
    if(child&&child.exitCode===null){child.kill('SIGTERM');await new Promise(ok=>child.once('exit',ok))}
    if(upstream){upstream.closeAllConnections();await new Promise(ok=>upstream.close(ok))}
    fs.rmSync(folder,{recursive:true,force:true});
}
