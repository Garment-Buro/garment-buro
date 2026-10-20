import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
import * as cartUtils from '../lib/cart/utils/cart.ts';
import * as browserStorage from '../lib/browser/utils/storage.ts';

const require=createRequire(import.meta.url),ts=require('typescript');
const {create}=require('zustand'),{persist,createJSONStorage}=require('zustand/middleware');
const item={id:'one',product_id:7,title:'Fixture',price:1000,quantity:1,image:'',size:'M',color:'black'};
const revision='a'.repeat(32),nextRevision='b'.repeat(32);
const snapshot=(items=[],rev=null)=>({items,revision:rev,updated_at_ms:0});
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no});return {promise,resolve,reject}};
const tick=()=>new Promise(resolve=>setImmediate(resolve));

function loadCart({read=async()=>snapshot(),write=async(_,data)=>snapshot(data.items,nextRevision),items=[item],dirty=true,baseKnown=true,baseRevision=null,memory=new Map(),seed=true}={}) {
    const timers=new Map(),storage={getItem:key=>memory.get(key)??null,setItem:(key,value)=>memory.set(key,value),removeItem:key=>memory.delete(key)};
    const loaded={exports:{}};
    const code=ts.transpileModule(fs.readFileSync(new URL('./cartStore.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
    vm.runInNewContext(code,{
        module:loaded,exports:loaded.exports,window:{crypto:globalThis.crypto},console,
        setTimeout:callback=>{const key=Symbol();timers.set(key,callback);return key},clearTimeout:key=>timers.delete(key),
        require:name=>{
            if(name==='zustand')return {create};
            if(name==='zustand/middleware')return {persist:(fn,options)=>persist(fn,{...options,storage:createJSONStorage(()=>storage)})};
            if(name==='@/lib/cart/utils/cart')return cartUtils;
            if(name==='@/lib/cart/snapshotSync')return require('../lib/cart/snapshotSync.ts');
            if(name==='@/lib/browser/utils/storage')return browserStorage;
            if(name==='@/lib/api/cart')return {getCartSnapshot:read,syncCartSnapshot:write};
            throw new Error(name);
        },
    });
    const store=loaded.exports.useCartStore;
    if(seed)store.setState({items:structuredClone(items),cartDirty:dirty,baseKnown,baseRevision,hasHydrated:true,cartId:'fixture-cart'});
    return {store,memory,flush:async()=>{const callbacks=[...timers.values()];timers.clear();for(const callback of callbacks)await callback();await tick()}};
}

test('a fresh visitor does not allocate or read a cart until the first edit',async()=>{
    const reads=[],writes=[],{store,memory}=loadCart({seed:false,
        read:async id=>{reads.push(id);return snapshot()},
        write:async(id,data)=>{writes.push({id,data});return snapshot(data.items,revision)}});
    await Promise.all([store.getState().initializeCart(),store.getState().initializeCart()]);
    assert.equal(reads.length,0);assert.equal(writes.length,0);
    assert.equal(store.getState().cartId,'');assert.equal(store.getState().baseKnown,false);
    assert.equal(store.getState().isCartInitialized,true);
    assert.equal(JSON.parse(memory.get('garment-buro-cart-storage')).state.cartId,'');
    store.getState().addItem(item);
    await store.getState().syncCartToServer({immediate:true});
    assert.equal(reads.length,1);assert.equal(writes.length,1);
    assert.match(reads[0],/^[a-f0-9-]{36}$/);
    assert.equal(writes[0].id,reads[0]);assert.equal(writes[0].data.expected_revision,null);
    assert.equal(writes[0].data.items[0].product_id,item.product_id);
    assert.equal(store.getState().baseRevision,revision);assert.equal(store.getState().cartDirty,false);
    let restoredReads=0;
    const restored=loadCart({seed:false,memory,read:async id=>{restoredReads++;assert.equal(id,reads[0]);return snapshot(writes[0].data.items,revision)}});
    await restored.store.getState().initializeCart();
    assert.equal(restoredReads,1);assert.equal(restored.store.getState().items.length,1);
});

test('an empty browser cache with an existing cart ID still restores remote items',async()=>{
    let reads=0;
    const {store}=loadCart({items:[],dirty:false,baseKnown:false,
        read:async()=>{reads++;return snapshot([item],revision)}});
    await store.getState().initializeCart();
    assert.equal(reads,1);assert.equal(store.getState().items[0].id,item.id);
    assert.equal(store.getState().baseRevision,revision);
});

test('two designs of one real size/color stay separate; normal SKU additions still merge', () => {
    const {store}=loadCart({items:[]});
    const first={...item,customization:{kind:'constructor',comment:'First design'}},second={...first,customization:{kind:'constructor',comment:'Second design'}};
    store.getState().addItem(first);store.getState().addItem(second);
    assert.equal(store.getState().items.length,2);
    assert.notEqual(store.getState().items[0].id,store.getState().items[1].id);
    assert.deepEqual(Array.from(store.getState().items,x=>x.customization.comment),['First design','Second design']);
    store.getState().updateItem(store.getState().items[0].id,{...first,customization:{kind:'constructor',comment:'Edited'}});
    assert.deepEqual(Array.from(store.getState().items,x=>x.customization.comment),['Edited','Second design']);
    store.getState().clearCart();store.getState().addItem(item);store.getState().addItem(item);
    assert.equal(store.getState().items.length,1);assert.equal(store.getState().items[0].quantity,2);
});

test('clean cache accepts a server clear regardless of browser clocks',async()=>{
    const writes=[],{store}=loadCart({dirty:false,baseRevision:revision,read:async()=>snapshot([],nextRevision),write:async(_,data)=>writes.push(data)});
    await store.getState().initializeCart();assert.equal(store.getState().items.length,0);assert.equal(writes.length,0);assert.equal(store.getState().baseRevision,nextRevision);
});
test('unknown edits never silently overwrite an existing server cart',async()=>{
    const writes=[],{store}=loadCart({baseKnown:false,read:async()=>snapshot([],revision),write:async(_,data)=>writes.push(data)});
    await store.getState().initializeCart();assert.equal(store.getState().items.length,1);assert.equal(store.getState().cartSyncConflict,true);assert.equal(writes.length,0);
    await store.getState().retryCartSync();assert.equal(writes.length,0);
});
test('clear during GET stays local and conflicts when its known base changed',async()=>{
    const get=deferred(),writes=[],{store}=loadCart({baseRevision:revision,read:()=>get.promise,write:async(_,data)=>writes.push(data)});
    const initializing=store.getState().initializeCart();await tick();store.getState().clearCart();get.resolve(snapshot([item],nextRevision));await initializing;await store.getState().syncCartToServer({immediate:true});
    assert.equal(store.getState().items.length,0);assert.equal(store.getState().cartSyncConflict,true);assert.equal(writes.length,0);
});
test('one PUT at a time; newer edits use the acknowledged revision',async()=>{
    const first=deferred(),writes=[];let active=0,peak=0;
    const {store}=loadCart({write:async(_,data)=>{active++;peak=Math.max(peak,active);writes.push(data);if(writes.length===1)await first.promise;active--;return snapshot(data.items,writes.length===1?revision:nextRevision)}});
    const saving=store.getState().syncCartToServer({immediate:true});await tick();store.getState().updateQuantity('one',2);const second=store.getState().syncCartToServer({immediate:true});store.getState().updateQuantity('one',3);await tick();assert.equal(writes.length,1);first.resolve();await Promise.all([saving,second]);
    assert.equal(peak,1);assert.deepEqual(writes.map(value=>value.items[0].quantity),[1,3]);assert.equal(writes[1].expected_revision,revision);assert.notEqual(writes[0].operation_id,writes[1].operation_id);assert.equal(store.getState().cartDirty,false);
});
test('lost acknowledgement replays the persisted exact request before newer edits after reload',async()=>{
    const writes=[],first=loadCart({write:async(_,data)=>{writes.push(structuredClone(data));throw new Error('lost acknowledgement')}});
    await first.store.getState().initializeCart();assert.equal(first.store.getState().cartSyncError,true);first.store.getState().updateQuantity('one',5);
    const second=loadCart({seed:false,memory:first.memory,read:async()=>snapshot([item],revision),write:async(_,data)=>{writes.push(structuredClone(data));return snapshot(data.items,writes.length===2?revision:nextRevision)}});
    await second.store.getState().initializeCart();assert.deepEqual(writes[1],writes[0]);assert.equal(writes[2].expected_revision,revision);assert.equal(writes[2].items[0].quantity,5);assert.equal(second.store.getState().pendingWrite,null);assert.equal(second.store.getState().cartDirty,false);
});
test('server-confirmed prices replace the acknowledged local snapshot',async()=>{
    const {store}=loadCart({write:async(_,data)=>snapshot(data.items.map(i=>({...i,price:1080})),revision)});await store.getState().initializeCart();assert.equal(store.getState().items[0].price,1080);assert.equal(store.getState().cartDirty,false);
});
test('revision conflicts retain edits and require a fresh explicit replacement',async()=>{
    const {CartRevisionConflictError}=await import('../lib/cart/snapshotSync.ts');let remote=snapshot([],revision),calls=0;const writes=[];
    const {store}=loadCart({read:async()=>remote,write:async(_,data)=>{writes.push(data);if(++calls===1)throw new CartRevisionConflictError();return snapshot(data.items,nextRevision)}});
    await store.getState().initializeCart();assert.equal(writes.length,0);await store.getState().resolveCartConflict('local');assert.equal(store.getState().cartSyncConflict,true);assert.equal(store.getState().items.length,1);
    remote=snapshot([],nextRevision);await store.getState().resolveCartConflict('local');assert.equal(writes[1].expected_revision,nextRevision);assert.equal(store.getState().cartSyncConflict,false);
});
test('server choice cannot erase an edit made during its fresh read',async()=>{
    const get=deferred();let calls=0;const {store}=loadCart({read:async()=>++calls===1?snapshot([],revision):get.promise});
    await store.getState().initializeCart();const resolving=store.getState().resolveCartConflict('server');await tick();store.getState().updateQuantity('one',4);get.resolve(snapshot([],nextRevision));await resolving;assert.equal(store.getState().items[0].quantity,4);assert.equal(store.getState().cartSyncConflict,true);
    await store.getState().resolveCartConflict('server');assert.equal(store.getState().items.length,0);assert.equal(store.getState().cartDirty,false);
});
test('failed initial read retains data and allows an explicit retry',async()=>{
    let calls=0;const writes=[];const {store}=loadCart({dirty:false,read:async()=>{if(++calls===1)throw new Error('unavailable');return snapshot([],revision)},write:async(_,data)=>writes.push(data)});
    await store.getState().initializeCart();assert.equal(store.getState().isCartInitialized,false);assert.equal(store.getState().cartSyncError,true);assert.equal(store.getState().items.length,1);await store.getState().retryCartSync();assert.equal(calls,2);assert.equal(store.getState().items.length,0);assert.equal(writes.length,0);
});
test('legacy persisted edits migrate with an unknown base',async()=>{
    const memory=new Map([['garment-buro-cart-storage',JSON.stringify({version:0,state:{items:[item],cartId:'fixture-cart',lastUpdatedAt:9999999999999}})]]);
    const writes=[],{store}=loadCart({seed:false,memory,read:async()=>snapshot([],revision),write:async(_,data)=>writes.push(data)});await store.getState().initializeCart();assert.equal(store.getState().cartSyncConflict,true);assert.equal(store.getState().items.length,1);assert.equal(writes.length,0);
});
test('initialization is single-flight and successful calls do not read again',async()=>{
    const get=deferred();let calls=0;const {store}=loadCart({items:[],dirty:false,read:()=>{calls++;return get.promise}});const first=store.getState().initializeCart(),second=store.getState().initializeCart();await tick();assert.equal(calls,1);get.resolve(snapshot());await Promise.all([first,second]);await store.getState().initializeCart();assert.equal(calls,1);
});

test('a clear made during PUT becomes the next versioned empty write',async()=>{
    const put=deferred(),writes=[];
    const {store}=loadCart({write:async(_,data)=>{writes.push(data);if(writes.length===1)await put.promise;return snapshot(data.items,writes.length===1?revision:nextRevision)}});
    const saving=store.getState().syncCartToServer({immediate:true});await tick();store.getState().clearCart();put.resolve();await saving;
    assert.equal(writes.length,2);assert.equal(writes[1].items.length,0);assert.equal(writes[1].expected_revision,revision);assert.equal(store.getState().items.length,0);assert.equal(store.getState().cartDirty,false);
});
