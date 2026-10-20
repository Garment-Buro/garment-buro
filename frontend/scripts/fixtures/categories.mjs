import assert from 'node:assert/strict';
import path from 'node:path';

export function createCategoryFixture({json}) {
    const state={},reads=[],sources=[],writes=[],held=[],heldWrites=[],changes=new Map();
    const root='/api/production/admin/assortment';
    const record=(kind,id)=>({id,code:`CATEGORY-${id}`,slug:`saved-category-${id}`,name:`Категория ${kind==='model-categories'?'моделей':'пресетов'} ${String(id).padStart(3,'0')}`,description:'Сохранённое описание\n'.repeat(150),is_active:id!==129,version:7,item_count:id===17?130:0,...changes.get(kind+'/'+id)});
    function handle(request,response,url) {
        const key=url.pathname;
        if(key===root+'/directory/selected' && ['model-categories','product-categories'].includes(url.searchParams.get('kind'))) {
            const kind=url.searchParams.get('kind');
            json(response,url.searchParams.getAll('ids').map(Number).map(id=>{const row=record(kind,id);return {id,name:row.name,code:kind==='product-categories'?row.slug:row.code,is_active:row.is_active}}));return true;
        }
        const page=key.match(/^\/api\/production\/admin\/assortment\/directory\/categories\/(model-categories|product-categories)$/);
        if(page) {
            const kind=page[1],query=Object.fromEntries(url.searchParams);reads.push({kind,...query});assert.equal(query.limit,'24');
            if(query.cursor&&state.failAppend){json(response,{detail:'Отказ страницы категорий'},503);return true;}
            if(query.cursor&&state.invalidCursor){json(response,{detail:{code:'invalid_cursor'}},422);return true;}
            const q=(query.query??'').toLowerCase(),offset=Number(query.cursor??0),rows=[...Array.from({length:130},(_,i)=>record(kind,i+1)),...(changes.has(kind+'/131')?[record(kind,131)]:[])].filter(row=>(!q||[row.name,row.code,row.slug].some(v=>v.toLowerCase().includes(q)))&&(!query.active||row.is_active===(query.active==='true')));
            const send=()=>json(response,{items:rows.slice(offset,offset+24).map(row=>({id:row.id,code:kind==='product-categories'?row.slug:row.code,name:row.name,is_active:row.is_active,version:1,item_count:row.item_count})),next_cursor:rows.length>offset+24?String(offset+24):null});
            if(state.holdSearch&&q.includes('моделей 00'))held.push(send);else send();return true;
        }
        const target=key.match(/^\/api\/production\/admin\/assortment\/(model-categories|product-categories)(?:\/(\d+))?$/);
        if(!target)return false;
        const [,kind,number]=target,id=Number(number);
        if(request.method==='GET') {
            assert.ok(number,'Retired full category list requested');sources.push({kind,id});
            if(state.failSource){json(response,{detail:'Отказ чтения категории'},503);return true;}
            const row=record(kind,id);
            json(response,state.incomplete?{id,name:row.name}:kind==='model-categories'?{id,name:row.name,code:row.code,is_active:row.is_active,version:row.version}:{id,name:row.name,slug:row.slug,description:row.description,is_active:row.is_active,version:row.version});return true;
        }
        let body='';request.on('data',chunk=>body+=chunk);request.on('end',()=>{
            const payload=JSON.parse(body);writes.push({kind,id,payload,method:request.method});
            const send=()=>{
                if(state.failSave)return json(response,{detail:'Отказ сохранения категории'},503);
                if(state.conflict){changes.set(kind+'/'+id,{...record(kind,id),version:record(kind,id).version+1});return json(response,{detail:'Версия категории изменилась'},409)}
                if(id)assert.equal(payload.expected_version,record(kind,id).version);
                else assert.equal(payload.expected_version,undefined);
                if(kind==='model-categories')assert.deepEqual(Object.keys(payload).sort(),['name','is_active',...(id?['expected_version']:[])].sort());
                changes.set(kind+'/'+(id||131),{...payload,version:id?payload.expected_version+1:1});json(response,record(kind,id||131),id?200:201);
            };
            if(state.holdSave)heldWrites.push(send);else send();
        });return true;
    }
    return {state,reads,sources,writes,held,heldWrites,record,handle,release(){held.splice(0).forEach(send=>send());heldWrites.splice(0).forEach(send=>send())}};
}

export async function checkCategoryFlow({page,until,fixture,proofDir}) {
    const {state,reads,sources,writes,record}=fixture;
    await page.getByRole('button',{name:'Модели',exact:true}).click();
    const models=page.locator('section[aria-label="Категории моделей"]'),cards=models.locator('[data-category]');
    await until(async()=>await cards.count()===24,'Category first page absent');
    assert.equal(sources.length,0,'Category cards must not prefetch editor sources');
    state.failAppend=true;await models.getByRole('button',{name:'Ещё категории моделей',exact:true}).click();
    await models.getByRole('alert').filter({hasText:'Отказ страницы категорий'}).waitFor();assert.equal(await cards.count(),24);
    state.failAppend=false;await models.getByRole('button',{name:'Ещё категории моделей',exact:true}).click();
    await until(async()=>await cards.count()===48,'Category append did not recover');
    while(await cards.count()<130){const before=await cards.count();await models.getByRole('button',{name:'Ещё категории моделей',exact:true}).click();await until(async()=>await cards.count()>before,'Category page did not append')}
    assert.equal(await cards.count(),130);
    state.failSource=true;await models.getByRole('button',{name:'Изменить категорию Категория моделей 130',exact:true}).click();
    let dialog=page.getByRole('dialog');await dialog.getByRole('alert').filter({hasText:'Отказ чтения категории'}).waitFor();assert.equal(await dialog.locator('form').count(),0);
    state.failSource=false;state.incomplete=true;await dialog.getByRole('button',{name:'Повторить загрузку категории',exact:true}).click();
    await dialog.getByRole('alert').filter({hasText:'неполную категорию'}).waitFor();assert.equal(await dialog.locator('form').count(),0);
    state.incomplete=false;await dialog.getByRole('button',{name:'Повторить загрузку категории',exact:true}).click();
    await dialog.getByRole('textbox',{name:'Название',exact:true}).fill('Черновик категории 130');
    state.failSave=true;await dialog.getByRole('button',{name:'Сохранить категорию',exact:true}).click();
    await dialog.getByRole('alert').filter({hasText:'Отказ сохранения категории'}).waitFor();assert.equal(await dialog.getByRole('textbox',{name:'Название',exact:true}).inputValue(),'Черновик категории 130');
    state.failSave=false;state.holdSave=true;await dialog.getByRole('button',{name:'Сохранить категорию',exact:true}).click();
    await until(()=>fixture.heldWrites.length===1,'Category write not held');assert.equal(await dialog.getByRole('button',{name:'Закрыть',exact:true}).isEnabled(),false);assert.equal(await dialog.getByRole('textbox',{name:'Название',exact:true}).isEnabled(),false);
    await dialog.locator('form').evaluate(form=>{for(let i=0;i<2;i++)form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))});assert.equal(writes.length,2);state.holdSave=false;fixture.heldWrites.splice(0).forEach(send=>send());await dialog.waitFor({state:'hidden'});
    assert.deepEqual(writes[0].payload,writes[1].payload);assert.equal(writes[1].payload.expected_version,7);assert.equal('code' in writes[1].payload,false);
    const categorySearch=models.getByRole('searchbox',{name:'Поиск категории',exact:true});await categorySearch.fill('Черновик категории 130');await until(async()=>await cards.count()===1&&await cards.first().getAttribute('data-category')==='130','Renamed category missing');await cards.first().getByRole('button').first().click();await page.getByRole('button',{name:'Категория: Черновик категории 130',exact:true}).waitFor();state.holdSearch=true;await categorySearch.fill('Категория моделей 00');await until(()=>fixture.held.length===1,'Category search not held');await categorySearch.fill('Категория моделей 129');await until(async()=>await cards.count()===1,'Latest category search missing');state.holdSearch=false;fixture.held.splice(0).forEach(send=>send());assert.match(await cards.innerText(),/129/);assert.equal(await page.getByRole('button',{name:'Категория: Черновик категории 130',exact:true}).count(),1);await page.getByRole('button',{name:'Все категории',exact:true}).click();
    const beforeNew=sources.length;await page.getByRole('button',{name:'Категория',exact:true}).click();dialog=page.getByRole('dialog');await dialog.getByLabel('Название',{exact:true}).fill('Новая категория после 130');assert.equal(sources.length,beforeNew);await dialog.getByRole('button',{name:'Сохранить категорию',exact:true}).click();await dialog.waitFor({state:'hidden'});
    assert.equal(writes.at(-1).method,'POST');assert.equal(writes.at(-1).payload.expected_version,undefined);await categorySearch.fill('Новая категория после 130');await until(async()=>await cards.count()===1&&await cards.first().getAttribute('data-category')==='131','Created model category missing');
    await page.getByRole('button',{name:'Изменить модель Модель 001',exact:true}).click();
    dialog=page.getByRole('dialog');await dialog.getByRole('combobox',{name:'Категория',exact:true}).waitFor();
    const category=dialog.getByRole('combobox',{name:'Категория',exact:true});
    await until(async()=>await category.locator('option').count()>=25,'Initial category choices missing');
    while(!await category.locator('option[value="130"]').count()){const before=await category.locator('option').count();await dialog.getByRole('button',{name:'Ещё категории моделей',exact:true}).click();await until(async()=>await category.locator('option').count()>before,'Category choices did not append')}
    await category.selectOption('130');await dialog.getByRole('searchbox',{name:'Поиск категории модели',exact:true}).fill('Ничего не найдено');await dialog.getByRole('status').filter({hasText:'Выбранная запись сохранена'}).waitFor();assert.equal(await category.inputValue(),'130');
    assert.equal(await category.locator('option[value="129"]').count(),0,'Inactive category cannot be newly assigned');
    await dialog.getByRole('button',{name:'Закрыть',exact:true}).click();
    await page.getByRole('button',{name:'Пресеты',exact:true}).click();await page.getByRole('button',{name:/Garment Buro/}).click();
    const products=page.locator('section[aria-label="Категории пресетов"]'),productCards=products.locator('[data-category]');await until(async()=>await productCards.count()===24,'Product category first page absent');
    while(await productCards.count()<130){const before=await productCards.count();await products.getByRole('button',{name:'Ещё категории пресетов',exact:true}).click();await until(async()=>await productCards.count()>before,'Product category page did not append')}
    await products.getByRole('button',{name:'Изменить категорию Категория пресетов 129',exact:true}).click();dialog=page.getByRole('dialog');
    assert.equal(await dialog.getByLabel('Адрес категории',{exact:true}).inputValue(),'saved-category-129');assert.equal(await dialog.getByLabel('Описание',{exact:true}).inputValue(),record('product-categories',129).description);
    for(const width of [320,390,736,1280]){await page.setViewportSize({width,height:850});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Category editor viewport '+width);assert.ok(await dialog.locator('form').evaluate(form=>form.parentElement.scrollWidth<=form.parentElement.clientWidth+1),'Category editor form '+width)}
    if(proofDir){await page.setViewportSize({width:390,height:850});await dialog.screenshot({path:path.join(proofDir,'category-editor-mobile.png')});await page.setViewportSize({width:1280,height:900});await dialog.screenshot({path:path.join(proofDir,'category-editor-desktop.png')})}
    await dialog.getByLabel('Название',{exact:true}).fill('Новое имя без смены адреса');state.conflict=true;await dialog.getByRole('button',{name:'Сохранить категорию',exact:true}).click();await dialog.getByRole('alert').filter({hasText:'Версия категории изменилась'}).waitFor();assert.equal(await dialog.getByLabel('Название',{exact:true}).inputValue(),'Новое имя без смены адреса');
    state.conflict=false;await dialog.getByRole('button',{name:'Загрузить актуальную категорию и заменить ввод',exact:true}).click();await until(async()=>await dialog.getByLabel('Название',{exact:true}).count()>0&&await dialog.getByLabel('Название',{exact:true}).inputValue()===record('product-categories',129).name,'Category did not reload');await dialog.getByLabel('Название',{exact:true}).fill('Новое имя без смены адреса');await dialog.getByRole('button',{name:'Сохранить категорию',exact:true}).click();await dialog.waitFor({state:'hidden'});
    const saved=writes.at(-1).payload;assert.equal(saved.expected_version,8);assert.equal(saved.slug,'saved-category-129');assert.equal(saved.is_active,false);assert.equal(saved.description,record('product-categories',129).description);
    await page.getByRole('button',{name:'Категория каталога',exact:true}).click();dialog=page.getByRole('dialog');await dialog.getByLabel('Название',{exact:true}).fill('Тёплая коллекция');assert.equal(await dialog.getByLabel('Адрес категории',{exact:true}).inputValue(),'teplaya-kollekciya');await dialog.getByLabel('Описание',{exact:true}).fill('Новое полное описание');await dialog.getByRole('button',{name:'Сохранить категорию',exact:true}).click();await dialog.waitFor({state:'hidden'});assert.equal(writes.at(-1).method,'POST');assert.equal(writes.at(-1).payload.slug,'teplaya-kollekciya');
    await products.getByRole('searchbox',{name:'Поиск категории',exact:true}).fill('Тёплая коллекция');await until(async()=>await productCards.count()===1&&await productCards.first().getAttribute('data-category')==='131','Created product category missing');
    await page.getByRole('button',{name:'Изменить пресет Модель 001',exact:true}).click();dialog=page.getByRole('dialog');const choice=dialog.getByRole('combobox',{name:'Категория',exact:true});await choice.waitFor();assert.equal(await choice.inputValue(),'17');
    await until(async()=>await choice.locator('option').count()>=25,'Initial product category choices missing');
    while(!await choice.locator('option[value="130"]').count()){const before=await choice.locator('option').count();await dialog.getByRole('button',{name:'Ещё категории пресетов',exact:true}).click();await until(async()=>await choice.locator('option').count()>before,'Product category choices did not append')}await choice.selectOption('130');await dialog.getByRole('searchbox',{name:'Поиск категории пресета',exact:true}).fill('Пустой поиск категории');await dialog.getByRole('status').filter({hasText:'Выбранная запись сохранена'}).waitFor();assert.equal(await choice.inputValue(),'130');
    for(const width of [320,390,736,1280]){await page.setViewportSize({width,height:850});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Category/preset viewport '+width)}
    if(proofDir){await page.setViewportSize({width:390,height:850});await dialog.screenshot({path:path.join(proofDir,'category-picker-mobile.png')})}
    await dialog.getByRole('button',{name:'Закрыть',exact:true}).click();await page.setViewportSize({width:1280,height:900});
    assert.ok(reads.length>0);
    return {modelCategories130:true,productCategories130:true,categorySourcesLazy:true,categorySearchRace:true,categoryReadRetry:true,categoryDraftAndSingleFlight:true,categoryConflictAndRawDescription:true,categoryExplicitReload:true,categoryFreshVersion:true,categoryFilterSurvivesSearch:true,categorySelectionPast100:true,categoryCreateBothKinds:true,categorySelectionAcrossEmptySearch:true,categoryEditorWidths:true,categoryWidths:[320,390,736,1280]};
}
