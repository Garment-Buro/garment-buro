import assert from 'node:assert/strict';
import path from 'node:path';

const widths=[320,390,599,600,736,899,900,1280];
const columnsAt=width=>width>=900?4:width>=600?3:2;
const layout=page=>page.locator('[data-search-product]').evaluateAll(nodes=>nodes.map(node=>{
    const box=node.getBoundingClientRect();
    return {id:Number(node.dataset.searchProduct),x:box.x,y:box.y,width:box.width,height:box.height};
}));
function verify(rows,width,ids){
    assert.deepEqual(rows.map(row=>row.id),ids,'DOM and keyboard order must follow the API');
    const first=rows.filter(row=>Math.abs(row.y-rows[0].y)<1);
    assert.equal(first.length,columnsAt(width),'Cards per row at '+width);
    assert.ok(rows.every(row=>row.width>0&&row.x>=0&&row.x+row.width<=width+1),'Cards must fit');
    assert.ok(first.every((row,i)=>i===0||row.x>first[i-1].x),'Visual order must match DOM order');
}

/** Shared by the standalone synthetic API gate and the real local stack. */
export async function checkStorefrontLayout({browser,base,screenshotDir}){
    const errors=[],checks=[],contexts=[];let release=()=>{};
    try{
        const api=await browser.newContext({serviceWorkers:'block'});contexts.push(api);
        const query='/api/catalog/products?min_price=0&sort=newest&limit=24';
        const response=await api.request.get(base+query);assert.equal(response.status(),200);
        const initial=await response.json(),ids=initial.items.map(row=>row.id);
        assert.equal(ids.length,24);
        for(const width of widths){
            const context=await browser.newContext({viewport:{width,height:844},javaScriptEnabled:false,serviceWorkers:'block'});
            try{
                const page=await context.newPage();await page.goto(base+'/catalog',{waitUntil:'domcontentloaded'});
                await page.locator('[data-search-product]').first().waitFor();
                verify(await layout(page),width,ids);
                assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'No-JS root overflow at '+width);
                checks.push({name:'responsive-without-javascript',width,columns:columnsAt(width)});
            }finally{await context.close()}
        }
        for(let run=1;run<=3;run++){
            const context=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block'});contexts.push(context);
            const page=await context.newPage();page.setDefaultTimeout(10000);
            page.on('pageerror',error=>errors.push(error.message));
            await page.addInitScript(()=>{
                localStorage.setItem('cookieConsent','accepted');window.__catalogShifts=[];
                new PerformanceObserver(list=>{for(const entry of list.getEntries())if(!entry.hadRecentInput)
                    window.__catalogShifts.push({time:entry.startTime,value:entry.value});
                }).observe({type:'layout-shift',buffered:true});
            });
            const scripts=[],reads=[];let held=true;
            release=()=>{held=false;scripts.splice(0).forEach(route=>route.continue().catch(()=>{}))};
            await context.route('**/_next/static/**/*.js',route=>{if(held)scripts.push(route);else return route.continue()});
            page.on('request',request=>{if(new URL(request.url()).pathname==='/api/catalog/products')reads.push(request.url())});
            await page.goto(base+'/catalog',{waitUntil:'commit'});
            await page.locator('[data-search-product]').nth(23).waitFor();
            await page.evaluate(()=>document.fonts.ready);
            const before=await layout(page);verify(before,1280,ids);
            await page.evaluate(()=>{window.__originalCatalogNodes=[...document.querySelectorAll('[data-search-product]')]});
            assert.ok(scripts.length>0,'Scripts must be held while checking server HTML');
            release();await page.waitForLoadState('domcontentloaded');
            await page.waitForFunction(()=>!document.querySelector('button[aria-label="Открыть избранное"]')?.disabled);
            await page.waitForTimeout(600);
            const after=await layout(page);verify(after,1280,ids);
            for(let i=0;i<before.length;i++)for(const key of ['x','y','width','height'])
                assert.ok(Math.abs(before[i][key]-after[i][key])<=1,`Hydration moved ${ids[i]} ${key}`);
            const identity=await page.evaluate(()=>window.__originalCatalogNodes.every((node,i)=>node===document.querySelectorAll('[data-search-product]')[i]));
            assert.equal(identity,true,'Hydration must preserve card nodes');assert.deepEqual(reads,[]);
            const shifts=await page.evaluate(()=>window.__catalogShifts),cls=shifts.reduce((sum,row)=>sum+row.value,0);
            assert.ok(cls<.01,'Unexpected initial catalog CLS: '+cls);
            checks.push({name:'stable-server-to-hydrated-layout',run,columnsBefore:4,columnsAfter:4,cls,identityPreserved:identity});
            if(run===1){
                const cards=page.locator('[data-search-product]'),summary=cards.first().getByRole('button',{name:/карточку$/});
                const next=cards.nth(1).getByRole('button',{name:/карточку$/});
                await summary.focus();await page.keyboard.press('Tab');
                assert.equal(await next.evaluate(node=>node===document.activeElement),true,'Closed actions must not add tab stops');
                await summary.focus();await page.keyboard.press('Enter');await page.keyboard.press('Tab');
                assert.equal(await cards.first().getByRole('button',{name:/в избранное$/}).evaluate(node=>node===document.activeElement),true);
                await page.keyboard.press('Tab');
                const create=cards.first().getByRole('link',{name:/создать изделие$/});
                assert.equal(await create.evaluate(node=>node===document.activeElement),true);
                assert.equal(await create.getAttribute('href'),`/constructor?productId=${ids[0]}`);
                const reference=await create.elementHandle();
                for(const width of widths){
                    await page.setViewportSize({width,height:844});
                    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
                    verify(await layout(page),width,ids);
                    assert.equal(await reference.evaluate(node=>node.isConnected&&node===document.activeElement),true,'Resize lost focus at '+width);
                    assert.equal(await summary.getAttribute('aria-expanded'),'true');
                    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
                }
                checks.push({name:'keyboard-and-resize',widths,focusedActionPreserved:true,expandedCardPreserved:true});
                await page.setViewportSize({width:1280,height:900});
                await summary.focus();await page.keyboard.press('Enter');await page.waitForTimeout(350);
                const closed=await layout(page);
                await page.keyboard.press('Enter');await page.waitForTimeout(350);
                const opened=await layout(page);
                assert.ok(opened[0].height>closed[0].height+30);
                assert.ok(Math.abs(opened[1].height-closed[1].height)<1,'Adjacent cards must not stretch');
                assert.ok(opened[4].y>=opened[0].y+opened[0].height+10,'Following row must clear open actions');
                await reference.dispose();await page.keyboard.press('Enter');await page.waitForTimeout(350);
                if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,'catalog-layout-desktop.png')});
                if(initial.next_cursor){
                    const more=await api.request.get(base+query+'&cursor='+encodeURIComponent(initial.next_cursor));assert.equal(more.status(),200);
                    const nextPage=await more.json(),expected=[...ids,...nextPage.items.map(row=>row.id)];
                    await page.getByRole('button',{name:'Показать ещё',exact:true}).click();
                    await page.waitForFunction(count=>document.querySelectorAll('[data-search-product]').length===count,expected.length);
                    assert.deepEqual((await layout(page)).map(row=>row.id),expected);assert.equal(new Set(expected).size,expected.length);
                    checks.push({name:'append-preserves-order-and-unique-ids',products:expected.length});
                }
                await page.setViewportSize({width:390,height:844});
                if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,'catalog-layout-mobile.png')});
            }
            await context.close();
        }
        assert.deepEqual(errors,[]);return {responsiveGrid:true,checks,errors};
    }finally{release();for(const context of contexts)await context.close()}
}
