import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError } from '../api/http.ts';
import { PublicProfileEditor } from './publicProfileEditor.ts';

const own = { id:41, slug:'member-one', display_name:'Анна', bio:'О себе', avatar_id:null, version:3, is_published:false };
const deferred = () => { let resolve; const promise = new Promise(ok => { resolve = ok; }); return {promise,resolve}; };
const transport = (overrides = {}) => ({
    load: async () => own,
    save: async value => ({...own,...value,version:value.version+1}),
    upload: async version => ({...own,avatar_id:73,version:version+1}),
    remove: async version => ({...own,avatar_id:null,version:version+1}),
    preview: async () => new Blob(['photo'],{type:'image/webp'}),
    ...overrides,
});

test('an absent public profile starts blank and saves an explicit private draft before publication', async () => {
    const editor = new PublicProfileEditor();
    const writes=[];
    await editor.setAccount('one',transport({load:async()=>null,save:async value=>{writes.push(value);return {...own,...value,version:1};}}));
    assert.deepEqual(editor.getSnapshot().draft,{slug:'',display_name:'',bio:''});
    assert.equal(await editor.setPublished(true),false);
    editor.setField('slug','member-one');editor.setField('display_name','Публичное имя');
    assert.equal(await editor.save(),true);
    assert.deepEqual(writes[0],{slug:'member-one',display_name:'Публичное имя',bio:'',version:0,is_published:false});
    assert.equal(editor.getSnapshot().profile.is_published,false);
    editor.dispose();
});

test('publication uses only saved fields and photos advance the version without discarding unsaved text', async () => {
    const editor = new PublicProfileEditor();
    const writes=[];
    await editor.setAccount('one',transport({save:async value=>{writes.push(value);return {...own,...value,version:value.version+1};}}));
    editor.setField('bio','Несохранённое');
    assert.equal(await editor.setPublished(true),false);
    assert.equal(await editor.upload(new Blob(['png'])),true);
    assert.equal(editor.getSnapshot().draft.bio,'Несохранённое');
    assert.equal(await editor.save(),true);
    assert.equal(writes[0].version,4);
    assert.equal(writes[0].is_published,false);
    assert.equal(await editor.setPublished(true),true);
    assert.equal(writes[1].version,5);
    assert.equal(writes[1].bio,'Несохранённое');
    assert.equal(writes[1].is_published,true);
    assert.equal(await editor.setPublished(false),true);
    assert.equal(writes[2].version,6);
    assert.equal(writes[2].is_published,false);
    editor.dispose();
});

test('409 preserves the draft and prevents writes until an explicit successful reload', async () => {
    const editor = new PublicProfileEditor();
    let failed=true, writes=0, loads=0;
    await editor.setAccount('one',transport({
        load:async()=>{loads++;return {...own,version:loads===1?3:8,bio:loads===1?'О себе':'Другой вкладки'};},
        save:async value=>{writes++;if(failed)throw new ApiError('Conflict',409);return {...own,...value,version:9};},
    }));
    editor.setField('bio','Мой черновик');
    assert.equal(await editor.save(),false);
    assert.equal(editor.getSnapshot().conflict,true);
    assert.equal(editor.getSnapshot().draft.bio,'Мой черновик');
    assert.equal(await editor.save(),false);assert.equal(writes,1);
    failed=false;await editor.reload();
    assert.equal(editor.getSnapshot().draft.bio,'Другой вкладки');
    assert.equal(editor.getSnapshot().conflict,false);
    editor.setField('bio','Обновлено');assert.equal(await editor.save(),true);
    assert.equal(editor.getSnapshot().profile.version,9);
    editor.dispose();
});

test('unpublishing immediately hides confirmed fields while retaining unsaved edits privately', async () => {
    const editor = new PublicProfileEditor();const writes=[];
    await editor.setAccount('one',transport({load:async()=>({...own,is_published:true}),save:async value=>{writes.push(value);return {...own,...value,version:value.version+1};}}));
    editor.setField('bio','Ещё не готово для публикации');
    assert.equal(await editor.setPublished(false),true);
    assert.deepEqual(writes[0],{slug:'member-one',display_name:'Анна',bio:'О себе',version:3,is_published:false});
    assert.equal(editor.getSnapshot().draft.bio,'Ещё не готово для публикации');
    assert.equal(editor.getSnapshot().profile.is_published,false);
    assert.equal(await editor.setPublished(true),false);
    assert.equal(await editor.save(),true);
    assert.equal(writes[1].bio,'Ещё не готово для публикации');assert.equal(writes[1].is_published,false);assert.equal(writes[1].version,4);
    editor.dispose();
});

test('network errors retain the form and retry sends the same confirmed version only once', async () => {
    const editor = new PublicProfileEditor();const pending=deferred();let attempts=0;
    await editor.setAccount('one',transport({save:async value=>{attempts++;if(attempts===1)throw new TypeError('Offline');await pending.promise;return {...own,...value,version:4};}}));
    editor.setField('display_name','Новое имя');
    assert.equal(await editor.save(),false);
    assert.equal(editor.getSnapshot().draft.display_name,'Новое имя');
    const retry=editor.save();assert.equal(await editor.save(),false);
    pending.resolve();assert.equal(await retry,true);
    assert.equal(attempts,2);assert.equal(editor.getSnapshot().error,null);
    editor.dispose();
});

test('account changes abort old reads and saves even if a transport resolves after cancellation', async () => {
    const editor = new PublicProfileEditor();const lateLoad=deferred(),lateSave=deferred();let signal;
    const loading=editor.setAccount('old',transport({load:async value=>{signal=value;return lateLoad.promise;}}));
    await editor.setAccount('new',transport({load:async()=>({...own,id:99,slug:'new-member'})}));
    assert.equal(signal.aborted,true);lateLoad.resolve(own);await loading;
    assert.equal(editor.getSnapshot().profile.id,99);
    await editor.setAccount('old',transport({save:async (_,value)=>{signal=value;return lateSave.promise;}}));
    editor.setField('bio','Old draft');const saving=editor.save();
    await editor.setAccount('new',transport({load:async()=>null}));
    assert.equal(signal.aborted,true);lateSave.resolve({...own,version:4});assert.equal(await saving,false);
    assert.equal(editor.getSnapshot().profile,null);assert.equal(editor.getSnapshot().draft.bio,'');
    editor.dispose();
});

test('private photo blob URLs are revoked on replacement, account change and unmount', async () => {
    const urls=new Set();let index=0;
    const editor = new PublicProfileEditor({create:()=>{const value='blob:test/'+(++index);urls.add(value);return value;},revoke:value=>urls.delete(value)});
    await editor.setAccount('one',transport({load:async()=>({...own,avatar_id:72})}));
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(editor.getSnapshot().avatarUrl,'blob:test/1');assert.equal(urls.size,1);
    await editor.upload(new Blob(['png']));await new Promise(resolve=>setImmediate(resolve));
    assert.equal(editor.getSnapshot().avatarUrl,'blob:test/2');assert.deepEqual([...urls],['blob:test/2']);
    await editor.setAccount('two',transport({load:async()=>null}));assert.equal(urls.size,0);
    await editor.setAccount('one',transport({load:async()=>({...own,avatar_id:72})}));await new Promise(resolve=>setImmediate(resolve));
    assert.equal(urls.size,1);editor.dispose();assert.equal(urls.size,0);
});

test('a late private photo cannot create an object URL after logout', async () => {
    const pending=deferred();let created=0,signal;
    const editor = new PublicProfileEditor({create:()=>{created++;return 'blob:old';},revoke:()=>{}});
    await editor.setAccount('one',transport({load:async()=>({...own,avatar_id:72}),preview:async (_,value)=>{signal=value;return pending.promise;}}));
    await editor.setAccount(null,null);assert.equal(signal.aborted,true);
    pending.resolve(new Blob(['photo']));await new Promise(resolve=>setImmediate(resolve));
    assert.equal(created,0);assert.equal(editor.getSnapshot().avatarUrl,null);
    editor.dispose();
});

test('removing a photo preserves edited text and unavailable previews do not prevent text saves', async () => {
    const editor = new PublicProfileEditor();
    await editor.setAccount('one',transport({load:async()=>({...own,avatar_id:72}),preview:async()=>{throw new TypeError('Unavailable');}}));
    await new Promise(resolve=>setImmediate(resolve));assert.equal(editor.getSnapshot().avatarError,true);
    editor.setField('bio','Новый текст');assert.equal(await editor.removeAvatar(),true);
    assert.equal(editor.getSnapshot().draft.bio,'Новый текст');assert.equal(editor.getSnapshot().avatarUrl,null);
    assert.equal(await editor.save(),true);assert.equal(editor.getSnapshot().profile.version,5);
    editor.dispose();
});
