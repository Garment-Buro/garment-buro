import assert from 'node:assert/strict';
import path from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';

export function createModelEditorFixture({json, modelRecord, referenceModels,detail}) {
    const state={scope:null,readMode:'ok',failRead:false,failSave:false,holdSave:false,holdUpload:false,badUpload:false,badFabrics:false,holdFabrics:false,badOptions:false,presetConflict:false,includeArchive:false,badSelectedSizes:false};
    const saves=[],uploads=[],heldSaves=[],heldUploads=[],heldFabrics=[],optionReads=[];
    return {state,saves,uploads,heldSaves,heldUploads,heldFabrics,optionReads,
        release(){heldFabrics.splice(0).forEach(send=>send());heldUploads.splice(0).forEach(send=>send());heldSaves.splice(0).forEach(send=>send())},
        handle(request,response,url){
            if(!state.scope)return false;
            const key=url.pathname;
            if(state.scope==='preset'&&key.includes('/editor-options/')){
                optionReads.push(key);
                if(state.badOptions&&['models','fabrics','sizes'].some(part=>key.endsWith('/'+part))){json(response,{items:[],next_cursor:130});return true}
            }
            if(state.scope==='preset'&&key.endsWith('/editor-options/models/130')){
                const ids=url.searchParams.getAll('selected_size_ids').map(Number);
                json(response,{id:130,name:'Модель 130',is_active:true,sizes:(state.badSelectedSizes?ids.slice(1):ids).map(id=>({id,code:id===7?'M':id===1007?'ARCHIVED':`SIZE-${String(id).padStart(3,'0')}`,is_active:id!==1007}))});return true;
            }
            if(state.scope==='preset'&&key==='/api/production/admin/assortment/products/1'&&request.method==='GET'){
                if(state.failRead){json(response,{detail:'Повторная загрузка недоступна'},503);return true}
                const row=detail();
                if(state.includeArchive)row.variants.push({...row.variants[0],id:92,sku:'ARCHIVED-SKU',garment_size_id:1007,size:'ARCHIVED',stock_quantity:4});
                if(state.readMode==='incomplete')delete row.desktop_video;
                if(state.readMode==='wrong-id')row.id=2;
                if(state.readMode==='bad-stock')row.variants[0].stock_quantity='15';
                if(state.readMode==='duplicate')row.variants.push({...row.variants[0]});
                json(response,row);return true;
            }
            if(state.scope==='model'&&key==='/api/production/admin/assortment/models/130'){
                if(request.method==='GET'){
                    if(state.failRead){json(response,{detail:'Повторная загрузка недоступна'},503);return true}
                    const row={...modelRecord(130)};
                    if(state.readMode==='incomplete')delete row.base_weight_g;
                    if(state.readMode==='wrong-id')row.id=129;
                    json(response,row);return true;
                }
                if(request.method==='PUT'){
                    let body='';request.on('data',chunk=>body+=chunk);request.on('end',()=>{
                        const payload=JSON.parse(body);saves.push(payload);
                        const send=()=>{
                            if(state.failSave)return json(response,{detail:'Проверочный отказ записи'},503);
                            if(payload.expected_version!==modelRecord(130).version)return json(response,{detail:{code:'crm_reference_version_conflict',message:'Модель изменилась в другой сессии'}},409);
                            referenceModels.set(130,{name:payload.name,version:payload.expected_version+1});json(response,{...modelRecord(130)});
                        };
                        if(state.holdSave)heldSaves.push(send);else send();
                    });return true;
                }
            }
            if(state.scope==='preset'&&key.endsWith('/editor-options/selected-fabrics')){
                const send=()=>json(response,state.badFabrics?[]:url.searchParams.getAll('ids').map(id=>({id:Number(id),name:`Ткань ${id}`,color_name:`Цвет ${id}`,color_hex:'#ffffff',is_active:true})));
                if(state.holdFabrics)heldFabrics.push(send);else send();return true;
            }
            if(state.scope==='preset'&&/^\/api\/production\/admin\/assortment\/products\/\d+$/.test(key)&&request.method==='PUT'){
                let body='';request.on('data',chunk=>body+=chunk);request.on('end',()=>{saves.push(JSON.parse(body));heldSaves.push(()=>state.presetConflict?json(response,{detail:{code:'catalog_product_version_conflict',message:'Пресет изменился в другой сессии'}},409):json(response,{detail:'Проверочный отказ записи'},503))});return true;
            }
            if(key==='/api/production/admin/assortment/media/public'&&request.method==='POST'){
                request.resume();uploads.push(key);
                const send=()=>json(response,state.badUpload?{url:'/unconfirmed.png'}:{id:444,url:'/uploads/form-proof.png'});
                if(state.holdUpload)heldUploads.push(send);else send();return true;
            }
            if(key==='/api/production/admin/assortment/media/public/444'){
                response.writeHead(200,{'Content-Type':'image/png'});response.end(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jQZkAAAAASUVORK5CYII=','base64'));return true;
            }
            return false;
        },
    };
}
const until=async(check,message)=>{for(let i=0;i<160;i++){if(await check())return;await delay(50)}throw new Error(message)};
const forceSubmit=dialog=>dialog.locator('form').evaluate(form=>{form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))});

export async function checkPresetOperationFlow(page,{fixture,png}){
    const {state,saves,uploads,heldUploads,heldSaves,heldFabrics}=fixture;
    state.scope='preset';state.includeArchive=true;
    try{
        const dialog=page.getByRole('dialog',{name:'Изменить пресет',exact:true});
        for(const mode of ['incomplete','wrong-id','bad-stock','duplicate']){
            state.readMode=mode;const optionsBefore=fixture.optionReads.length;
            await page.reload();await dialog.getByRole('alert').filter({hasText:'неполные или неверные данные пресета'}).waitFor();
            assert.equal(await dialog.locator('form').count(),0,'Invalid source must not open an editable preset');
            assert.equal(fixture.optionReads.length,optionsBefore,'Invalid source must not prefetch editor options');
        }
        state.readMode='ok';state.badOptions=true;await page.reload();
        await dialog.getByRole('button',{name:'Повторить поиск моделей',exact:true}).waitFor();
        await dialog.getByRole('button',{name:'Повторить поиск тканей',exact:true}).waitFor();
        await dialog.getByRole('button',{name:'Повторить поиск размеров',exact:true}).waitFor();
        assert.equal(await dialog.getByRole('button',{name:'ARCHIVED · архив',exact:true}).getAttribute('aria-pressed'),'true');
        assert.equal(await dialog.getByRole('button',{name:'Цвет 129 · Ткань 129',exact:true}).getAttribute('aria-pressed'),'true');
        assert.equal(await dialog.getByRole('combobox',{name:'Производственная модель',exact:true}).inputValue(),'130');
        state.badOptions=false;
        await dialog.getByRole('button',{name:'Повторить поиск моделей',exact:true}).click();
        await dialog.getByRole('button',{name:'Повторить поиск тканей',exact:true}).click();
        await dialog.getByRole('button',{name:'Повторить поиск размеров',exact:true}).click();
        await until(async()=>!await dialog.getByRole('button',{name:/Повторить поиск (моделей|тканей|размеров)/}).count(),'Option retry did not recover');
        for(let i=0;i<5;i++){
            await dialog.getByRole('button',{name:'Ещё размеры',exact:true}).click();
            await until(async()=>!await dialog.getByRole('button',{name:'Ещё размеры',exact:true}).count()||!await dialog.getByRole('button',{name:'Ещё размеры',exact:true}).isDisabled(),'Size continuation did not settle');
        }
        await dialog.getByRole('button',{name:'SIZE-130',exact:true}).click();
        await until(async()=>!await dialog.getByRole('button',{name:'Сохранить пресет',exact:true}).isDisabled(),'New selected size context did not settle');
        await dialog.getByRole('searchbox',{name:'Поиск размера',exact:true}).fill('нет совпадений');
        await until(async()=>!await dialog.getByRole('button',{name:'SIZE-001',exact:true}).count(),'Empty size search did not settle');
        assert.equal(await dialog.getByRole('button',{name:'SIZE-130',exact:true}).getAttribute('aria-pressed'),'true');
        assert.equal(await dialog.getByRole('button',{name:'ARCHIVED · архив',exact:true}).getAttribute('aria-pressed'),'true');
        await dialog.getByRole('button',{name:'SIZE-130',exact:true}).click();
        await until(async()=>!await dialog.getByRole('button',{name:'Сохранить пресет',exact:true}).isDisabled(),'Deselected size context did not settle');
        state.badSelectedSizes=true;await page.reload();
        await dialog.getByRole('alert').filter({hasText:'Сервер вернул не все выбранные размеры'}).waitFor();
        assert.equal(await dialog.getByRole('button',{name:'Сохранить пресет',exact:true}).isDisabled(),true);
        state.badSelectedSizes=false;await dialog.getByRole('button',{name:'Повторить загрузку вариантов',exact:true}).click();
        await until(async()=>!await dialog.getByRole('button',{name:'Сохранить пресет',exact:true}).isDisabled(),'Selected sizes retry did not settle');
        state.badFabrics=true;await page.reload();
        await dialog.getByRole('alert').filter({hasText:'Сервер вернул не все выбранные ткани'}).waitFor();
        assert.equal(await dialog.getByRole('button',{name:'Сохранить пресет',exact:true}).isDisabled(),true);
        state.badFabrics=false;state.holdFabrics=true;
        await dialog.getByRole('button',{name:'Повторить загрузку вариантов',exact:true}).click();
        await until(()=>heldFabrics.length===1,'Reference retry was not held');
        await dialog.getByRole('status').filter({hasText:'Проверка модели и тканей'}).waitFor();
        assert.equal(await dialog.getByRole('button',{name:'Сохранить пресет',exact:true}).isDisabled(),true);
        heldFabrics.shift()();state.holdFabrics=false;
        await until(async()=>!await dialog.getByRole('button',{name:'Сохранить пресет',exact:true}).isDisabled(),'Reference retry did not recover');
        state.badUpload=true;
        const front=dialog.getByLabel('Основное изображение',{exact:true});
        await front.setInputFiles({name:'same.png',mimeType:'image/png',buffer:png});
        await dialog.getByRole('alert').filter({hasText:'Сервер не подтвердил загрузку изображения'}).waitFor();
        assert.equal(await front.inputValue(),'');
        assert.equal(await dialog.getByRole('img',{name:'Основное изображение',exact:true}).getAttribute('src'),'/left.webp');
        state.badUpload=false;state.holdUpload=true;
        await dialog.getByText('Дополнительные галереи',{exact:true}).click();
        const input=dialog.getByLabel('Дополнительные фото',{exact:true});
        const beforeUploads=uploads.length,beforeSaves=saves.length;
        await input.setInputFiles([{name:'first.png',mimeType:'image/png',buffer:png},{name:'second.png',mimeType:'image/png',buffer:png}]);
        await until(()=>heldUploads.length===1,'Preset batch upload was not held');
        await forceSubmit(dialog);
        assert.equal(saves.length,beforeSaves,'Save must not overlap a batch upload');
        assert.equal(await dialog.getByRole('button',{name:'Закрыть',exact:true}).isDisabled(),true);
        heldUploads.shift()();await until(()=>heldUploads.length===1&&uploads.length===beforeUploads+2,'Second file must remain inside the same operation');
        await forceSubmit(dialog);assert.equal(saves.length,beforeSaves);
        heldUploads.shift()();state.holdUpload=false;
        await dialog.getByRole('status').filter({hasText:'Изображения загружены'}).waitFor();
        assert.equal(await input.inputValue(),'','Successful batch must reset the file input');
        await dialog.getByLabel('Название',{exact:true}).fill('Черновик после загрузки');
        await forceSubmit(dialog);await until(()=>heldSaves.length===1,'Preset save was not held');
        await delay(100);assert.equal(saves.length,beforeSaves+1,'Two forced submit events must issue one preset write');
        assert.equal(await dialog.getByRole('button',{name:'Отмена',exact:true}).isDisabled(),true);
        heldSaves.shift()();await dialog.getByRole('alert').filter({hasText:'Проверочный отказ записи'}).waitFor();
        assert.equal(await dialog.getByLabel('Название',{exact:true}).inputValue(),'Черновик после загрузки');
        assert.equal(saves.at(-1).gallery_images,'/gallery.webp,/uploads/form-proof.png,/uploads/form-proof.png');
        assert.equal(saves.at(-1).stock_quantity,8);assert.equal(saves.at(-1).variants[0].stock_quantity,15);
        assert.equal(saves.at(-1).video_src,'/video.webm');assert.equal(saves.at(-1).size_chart_img_1,'/chart-1.webp');
        assert.equal(saves.at(-1).desktop_video_poster,'/poster.webp');assert.equal(saves.at(-1).size_chart_img_2,null);
        assert.equal(saves.at(-1).image_left,'/left.webp');
        assert.ok(saves.at(-1).variants.some(row=>row.id===92&&row.garment_size_id===1007&&row.stock_quantity===4),'Archived selected variant must survive all page reads and save');
        state.presetConflict=true;await forceSubmit(dialog);await until(()=>heldSaves.length===1,'Preset conflict write was not held');
        heldSaves.shift()();await dialog.getByRole('alert').filter({hasText:'Пресет изменился'}).waitFor();
        await dialog.getByText('Открыть актуальную версию',{exact:true}).click();
        state.failRead=true;await dialog.getByRole('button',{name:'Заменить черновик актуальной версией',exact:true}).click();
        await dialog.getByRole('alert').filter({hasText:'Повторная загрузка недоступна'}).waitFor();
        assert.equal(await dialog.locator('form').count(),0);
        await dialog.getByRole('button',{name:'Вернуться к черновику',exact:true}).click();
        assert.equal(await dialog.getByLabel('Название',{exact:true}).inputValue(),'Черновик после загрузки');
        assert.equal(await dialog.getByRole('img',{name:'Основное изображение',exact:true}).getAttribute('src'),'/left.webp');
        assert.equal(await dialog.getByRole('button',{name:'Сохранить пресет',exact:true}).isDisabled(),true);
        for(const [width,height] of [[320,850],[390,850],[736,390],[1280,850]]){
            await page.setViewportSize({width,height});
            assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Preset page overflow ${width}`);
            assert.ok(await dialog.locator('form').evaluate(form=>form.parentElement.scrollWidth<=form.parentElement.clientWidth+1),`Preset form overflow ${width}`);
            if(width===390&&process.env.GB_ADMIN_PROOF_DIR)await dialog.screenshot({path:path.join(process.env.GB_ADMIN_PROOF_DIR,'preset-fields-mobile.png'),animations:'disabled'});
        }
        await dialog.getByRole('button',{name:'Закрыть',exact:true}).click();
        await dialog.waitFor({state:'detached'});
        return {presetBatchLock:true,presetSingleFlight:true,presetDraftAfterFailure:true,presetFileInputReset:true,presetMissingReferenceRejected:true,presetReferenceRetryFresh:true,presetSourceValidated:true,presetOptionsAfterSource:true,presetOptionsRetry:true,presetUploadReceipt:true,presetHiddenMediaAndStock:true,presetDraftAfterReloadFailure:true,presetWidths:true,presetSizePages130:true,presetSizeChoiceAcrossSearch:true,presetSelectedArchivedSize:true,presetIncompleteSizesRejected:true};
    }finally{state.scope=null;state.holdUpload=false;state.readMode='ok';state.badOptions=false;state.badUpload=false;state.presetConflict=false;state.failRead=false;state.includeArchive=false;state.badSelectedSizes=false;fixture.release()}
}

export async function checkModelOperationFlow(page,{fixture,modelRecord,referenceModels,png}){
    const {state,saves,uploads,heldSaves,heldUploads}=fixture;
    state.scope='model';
    await page.getByRole('textbox',{name:'Поиск модели',exact:true}).fill('Модель 130');
    const open=()=>page.getByRole('button',{name:`Изменить модель ${modelRecord(130).name}`,exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'Изменить модель',exact:true});
    try{
        for(const mode of ['incomplete','wrong-id']){
            state.readMode=mode;await open();await dialog.getByRole('alert').waitFor();
            assert.equal(await dialog.locator('form').count(),0,'Untrusted source must not open an editable model');
            await dialog.getByRole('button',{name:'Закрыть',exact:true}).click();
        }
        state.readMode='ok';await open();await dialog.getByLabel('Название',{exact:true}).fill('Модель с сохранённым черновиком');
        const input=dialog.locator('input[type=file]');const file={name:'same-chart.png',mimeType:'image/png',buffer:png};
        const startSaves=saves.length,startUploads=uploads.length;
        state.badUpload=true;await input.setInputFiles(file);
        await dialog.getByRole('alert').filter({hasText:'Сервер не подтвердил загрузку'}).first().waitFor();
        assert.equal(await input.inputValue(),'');
        assert.equal(await dialog.locator('img[alt="Загруженная таблица размеров"]').count(),0);
        state.badUpload=false;state.holdUpload=true;await input.setInputFiles(file);
        await until(()=>heldUploads.length===1,'Model upload was not held');await forceSubmit(dialog);
        assert.equal(saves.length,startSaves);
        assert.equal(await dialog.getByRole('button',{name:'Закрыть',exact:true}).isDisabled(),true);
        heldUploads.shift()();state.holdUpload=false;
        await dialog.locator('img[alt="Загруженная таблица размеров"]').waitFor();
        assert.equal(await dialog.locator('img[alt="Загруженная таблица размеров"]').getAttribute('src'),'/api/production/admin/assortment/media/public/444');
        state.holdSave=true;state.failSave=true;await forceSubmit(dialog);
        await until(()=>heldSaves.length===1,'Model save was not held');await delay(100);
        assert.equal(saves.length,startSaves+1,'Two forced submit events must issue one model write');
        assert.equal(await dialog.getByRole('button',{name:'Закрыть',exact:true}).isDisabled(),true);
        heldSaves.shift()();state.holdSave=false;
        await dialog.getByRole('alert').filter({hasText:'Проверочный отказ записи'}).waitFor();
        assert.equal(await dialog.getByLabel('Название',{exact:true}).inputValue(),'Модель с сохранённым черновиком');
        assert.equal(saves.at(-1).size_chart_media_object_id,444);
        const previous=modelRecord(130);referenceModels.set(130,{name:previous.name,version:previous.version+1});
        state.failSave=false;await dialog.getByRole('button',{name:'Сохранить модель',exact:true}).click();
        await dialog.getByRole('alert').filter({hasText:'Модель изменилась'}).waitFor();
        assert.equal(await dialog.getByRole('button',{name:'Сохранить модель',exact:true}).isDisabled(),true);
        state.failRead=true;await dialog.getByRole('button',{name:'Перечитать модель и заменить черновик',exact:true}).click();
        await dialog.getByRole('alert').filter({hasText:'Повторная загрузка недоступна'}).waitFor();
        assert.equal(await dialog.locator('form').count(),0);
        await dialog.getByRole('button',{name:'Вернуться к черновику',exact:true}).click();
        assert.equal(await dialog.getByLabel('Название',{exact:true}).inputValue(),'Модель с сохранённым черновиком');
        assert.equal(await dialog.locator('img[alt="Загруженная таблица размеров"]').getAttribute('src'),'/api/production/admin/assortment/media/public/444');
        state.failRead=false;await dialog.getByRole('button',{name:'Перечитать модель и заменить черновик',exact:true}).click();
        await until(async()=>await dialog.getByLabel('Название',{exact:true}).inputValue()===modelRecord(130).name,'Fresh source was not installed before editing');
        await dialog.getByLabel('Название',{exact:true}).fill('Модель 130 после конфликта');
        for(const [width,height] of [[320,850],[390,850],[736,390],[1280,850]]){
            await page.setViewportSize({width,height});
            if(width===390&&process.env.GB_ADMIN_PROOF_DIR)await dialog.screenshot({path:path.join(process.env.GB_ADMIN_PROOF_DIR,'model-editor-mobile.png'),animations:'disabled'});
            assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Model page overflow ${width}`);
            assert.ok(await dialog.locator('form').evaluate(form=>form.parentElement.scrollWidth<=form.parentElement.clientWidth+1),`Model form overflow ${width}`);
        }
        if(process.env.GB_ADMIN_PROOF_DIR)await dialog.screenshot({path:path.join(process.env.GB_ADMIN_PROOF_DIR,'model-editor-final.png'),animations:'disabled'});
        await forceSubmit(dialog);await dialog.waitFor({state:'detached'});
        assert.equal(saves.at(-1).expected_version,previous.version+1);
        assert.equal(saves.at(-1).name,'Модель 130 после конфликта','Input after the explicit reload must reach the saved payload');
        assert.equal(uploads.length,startUploads+2,'Save retry must not reupload the confirmed chart');
        assert.equal(saves.at(-1).sizes.length,1);
        return {modelSingleFlight:true,modelUploadLock:true,modelUploadReceipt:true,modelSourceIdentity:true,modelConflictReload:true,modelDraftAfterFailedReload:true,modelNoReuploadOnSave:true,modelEditorWidths:true};
    }finally{state.scope=null;state.failRead=false;state.failSave=false;state.readMode='ok';fixture.release()}
}
