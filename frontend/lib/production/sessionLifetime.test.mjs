import assert from 'node:assert/strict';
import fs from 'node:fs';
import {registerHooks} from 'node:module';
import test from 'node:test';
import {fileURLToPath,pathToFileURL} from 'node:url';
const frontend=fileURLToPath(new URL('../../',import.meta.url));
registerHooks({resolve(specifier,context,next){
    if(specifier.startsWith('@/'))specifier=pathToFileURL(frontend+specifier.slice(2)).href;
    if(specifier.startsWith('file:')||specifier.startsWith('.')){
        const url=new URL(specifier,context.parentURL);
        if(!/\.[a-z]+$/i.test(url.pathname)&&fs.existsSync(fileURLToPath(url)+'.ts'))return next(url.href+'.ts',context);
    }
    return next(specifier,context);
}});
const data=new Map();
globalThis.window=Object.assign(new EventTarget(),{localStorage:{getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value),removeItem:key=>data.delete(key)},setTimeout,clearTimeout});
globalThis.document=Object.assign(new EventTarget(),{visibilityState:'visible'});
let tail=Promise.resolve();
Object.defineProperty(globalThis,'navigator',{configurable:true,value:{locks:{request:(_name,operation)=>{
    const result=tail.then(operation);tail=result.catch(()=>{});return result;
}}}});
const {useProductionAuthStore:store}=await import('../../store/productionAuthStore.ts');
const {ApiError}=await import('../api/http.ts');
const {publishProductionSession,PRODUCTION_SESSION_KEY}=await import('./sessionCoordination.ts');
const employee={id:7,name:'Тестовый сотрудник',stations:[],can_administer:true,admin_scope:'system'};
const deferred=()=>{let resolve,reject;const promise=new Promise((ok,fail)=>{resolve=ok;reject=fail});return {promise,resolve,reject}};
const reset=()=>{data.clear();store.setState({user:null,isAuthenticated:false,isSessionReady:false,error:'',sessionEpoch:null})};
const signedIn=()=>{publishProductionSession({epoch:'test-login',phase:'active'});store.setState({user:employee,isAuthenticated:true,isSessionReady:true,error:'',sessionEpoch:'test-login'})};

test('a late initialize response cannot reopen production after logout',async()=>{
    reset();const pending=deferred(),started=deferred();
    globalThis.fetch=async url=>{if(url==='/api/production/me'){started.resolve();return pending.promise}return Response.json({})};
    const initialize=store.getState().initialize();await started.promise;
    const logout=store.getState().logout();assert.equal(store.getState().isAuthenticated,false);
    pending.resolve(Response.json(employee));await Promise.all([initialize,logout]);
    assert.equal(store.getState().user,null);assert.equal(store.getState().isAuthenticated,false);
});
test('late unauthorized results from an older login never sign out the next employee',async()=>{
    reset();signedIn();const pending=deferred();
    const command=store.getState().runAuthenticated(()=>pending.promise);
    const rejection=assert.rejects(command,{name:'AbortError'});
    store.setState({user:{...employee,id:8},sessionEpoch:'new-login',isAuthenticated:true});
    pending.reject(new ApiError('Old unauthorized',401));await rejection;
    assert.equal(store.getState().user.id,8);assert.equal(store.getState().isAuthenticated,true);
});
test('a signed-out caller cannot start a production command',async()=>{
    reset();let calls=0;
    await assert.rejects(store.getState().runAuthenticated(async()=>{calls++}),{name:'AbortError'});
    assert.equal(calls,0);
});

test('commands from a previous login are rejected even when the same employee signs in again',async()=>{
    reset();signedIn();const old=store.getState().sessionEpoch,pending=deferred();
    const command=store.getState().runAuthenticated(()=>pending.promise);
    const rejection=assert.rejects(command,{name:'AbortError'});
    globalThis.fetch=async url=>Response.json(url.endsWith('/me')?employee:{});
    await store.getState().login('123456');assert.notEqual(store.getState().sessionEpoch,old);
    pending.resolve({saved:true});await rejection;assert.equal(store.getState().user.id,7);
});
test('cookie logout finishes before a queued new login starts and cannot erase it afterwards',async()=>{
    reset();signedIn();const started=deferred(),pending=deferred(),order=[];
    globalThis.fetch=async url=>{
        if(url.endsWith('/logout')){order.push('logout-start');started.resolve();await pending.promise;order.push('logout-end');return Response.json({})}
        order.push(url.endsWith('/login')?'login':'me');return Response.json(url.endsWith('/me')?{...employee,id:8}:{});
    };
    const logout=store.getState().logout();await started.promise;
    assert.equal(store.getState().user,null);const login=store.getState().login('654321');
    await Promise.resolve();assert.deepEqual(order,['logout-start']);
    pending.resolve();await Promise.all([logout,login]);
    assert.deepEqual(order,['logout-start','logout-end','login','me']);assert.equal(store.getState().user.id,8);
});
test('logout waits for an old in-flight login cookie response and closes it afterwards',async()=>{
    reset();const started=deferred(),pending=deferred(),order=[];
    globalThis.fetch=async url=>{
        if(url.endsWith('/login')){order.push('login');started.resolve();await pending.promise;return Response.json({})}
        order.push(url);return Response.json({});
    };
    const login=store.getState().login('123456'),rejection=assert.rejects(login,{name:'AbortError'});await started.promise;
    const logout=store.getState().logout();pending.resolve();await Promise.all([rejection,logout]);
    assert.deepEqual(order,['login','/api/production/auth/logout']);assert.equal(store.getState().isAuthenticated,false);
});
test('initialization is single flight and a recheck preserves an existing editing lifetime',async()=>{
    reset();const started=deferred(),pending=deferred();let reads=0;
    globalThis.fetch=async()=>{reads++;started.resolve();return pending.promise};
    const first=store.getState().initialize(),second=store.getState().initialize();assert.equal(first,second);
    await started.promise;pending.resolve(Response.json(employee));await first;
    const epoch=store.getState().sessionEpoch;globalThis.fetch=async()=>{reads++;return Response.json(employee)};
    await store.getState().initialize();assert.equal(store.getState().sessionEpoch,epoch);assert.equal(reads,2);
});
test('a failed logout stays signed out across reinitialization even if the cookie survives',async()=>{
    reset();signedIn();let reads=0;
    globalThis.fetch=async url=>{if(url.endsWith('/logout'))throw new TypeError('offline');reads++;return Response.json(employee)};
    await store.getState().logout();assert.match(store.getState().error,/Сервер не подтвердил/);
    await store.getState().initialize();assert.equal(reads,0);assert.equal(store.getState().user,null);
    assert.equal(JSON.parse(data.get(PRODUCTION_SESSION_KEY)).phase,'signed_out');
});
test('only a current unauthorized command invalidates the production session',async()=>{
    reset();signedIn();await assert.rejects(store.getState().runAuthenticated(async()=>{throw new TypeError('offline')}),/offline/);
    assert.equal(store.getState().isAuthenticated,true);
    await assert.rejects(store.getState().runAuthenticated(async()=>{throw new ApiError('Expired',401)}),{status:401});
    assert.equal(store.getState().isAuthenticated,false);assert.equal(JSON.parse(data.get(PRODUCTION_SESSION_KEY)).phase,'signed_out');
});
const remote=()=>{const event=new Event('storage');Object.defineProperty(event,'key',{value:PRODUCTION_SESSION_KEY});window.dispatchEvent(event)};
test('remote pending intent invalidates commands immediately and delayed events use the latest shared marker',async()=>{
    reset();signedIn();const pending=deferred();
    const command=store.getState().runAuthenticated(()=>pending.promise),rejection=assert.rejects(command,{name:'AbortError'});
    publishProductionSession({epoch:'remote-out',phase:'pending'});remote();assert.equal(store.getState().user,null);
    let reads=0;globalThis.fetch=async()=>{reads++;return Response.json({...employee,id:9})};
    publishProductionSession({epoch:'remote-login',phase:'active'});remote();
    await store.getState().initialize();assert.equal(store.getState().user.id,9);
    remote();assert.equal(reads,1);assert.equal(store.getState().sessionEpoch,'remote-login');
    pending.resolve('old data');await rejection;
});
test('shared logout markers contain only lifetime metadata, never the code or employee fields',async()=>{
    reset();globalThis.fetch=async url=>Response.json(url.endsWith('/me')?employee:{});
    await store.getState().login('123456');const marker=JSON.parse(data.get(PRODUCTION_SESSION_KEY));
    assert.deepEqual(Object.keys(marker).sort(),['epoch','phase']);assert.equal(marker.phase,'active');
    assert.equal(JSON.stringify([...data]).includes('123456'),false);assert.equal(JSON.stringify([...data]).includes(employee.name),false);
});
test('read, write and media assortment helpers cannot bypass the production lifetime guard',async()=>{
    const {readAssortment,saveAssortment,uploadAssortmentMedia}=await import('../api/productionAssortment.ts');
    reset();let calls=0;globalThis.fetch=async()=>{calls++;return Response.json({})};
    for(const action of [()=>readAssortment('fabrics'),()=>saveAssortment('fabrics','POST',{}),()=>uploadAssortmentMedia(new File(['x'],'fixture.png'),'public')])
        await assert.rejects(action(),{name:'AbortError'});
    assert.equal(calls,0);
});
test('cookie changes cannot start without real shared storage or the browser lock',async()=>{
    reset();let calls=0;globalThis.fetch=async()=>{calls++;return Response.json({})};
    const saved=window.localStorage,savedLocks=navigator.locks;
    try{
        window.localStorage={getItem(){return null},setItem(){throw new DOMException('Denied','SecurityError')},removeItem(){}};
        await assert.rejects(store.getState().login('123456'),/разрешите хранение/);
        assert.equal(calls,0);assert.equal(store.getState().isAuthenticated,false);
        window.localStorage=saved;navigator.locks=undefined;
        await assert.rejects(store.getState().login('123456'),/Обновите браузер/);assert.equal(calls,0);
    }finally{window.localStorage=saved;navigator.locks=savedLocks}
});
