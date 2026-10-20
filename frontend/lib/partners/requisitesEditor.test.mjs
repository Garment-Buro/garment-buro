import assert from 'node:assert/strict';
import test from 'node:test';
import {ApiError} from '../api/http.ts';
import {RequisitesEditor} from './requisitesEditor.ts';
const stored={version:1,entity_type:'self_employed',recipient_name:'Тестовый получатель',tax_id:'123456789012',kpp:null,bank_name:'Тестовый банк',bic:'044525225',correspondent_account:'30101810400000000225',settlement_account:'40802810900000000001',updated_at:'2026-10-18T10:00:00Z'};
const deferred=()=>{let resolve;return {promise:new Promise(ok=>{resolve=ok}),resolve:value=>resolve(value)}};
const transport=(changes={})=>({read:async()=>stored,save:async draft=>({...draft,version:draft.expected_version+1,updated_at:stored.updated_at}),...changes});
test('bank details are lazy and a failed read cannot become an empty overwrite',async()=>{
    const editor=new RequisitesEditor();let reads=0,writes=0;
    editor.setAccount('one',transport({read:async()=>{reads++;throw new TypeError('offline')},save:async()=>{writes++;return stored}}));
    assert.equal(reads,0);assert.equal(await editor.save(),false);
    assert.equal(await editor.load(),false);assert.equal(editor.getSnapshot().loaded,false);
    editor.setField('recipient_name','Нельзя');assert.equal(await editor.save(),false);assert.equal(writes,0);
    editor.dispose();
});
test('a confirmed null read allows creation and saved payload excludes response metadata',async()=>{
    const editor=new RequisitesEditor(),writes=[];
    editor.setAccount('one',transport({read:async()=>null,save:async draft=>{writes.push(draft);return {...draft,version:draft.expected_version+1,updated_at:stored.updated_at}}}));
    await editor.load();editor.setField('recipient_name','Новый получатель');
    assert.equal(await editor.save(),true);assert.equal(writes[0].updated_at,undefined);assert.equal(writes[0].version,undefined);assert.equal(writes[0].expected_version,0);
    assert.equal(editor.getSnapshot().record.recipient_name,'Новый получатель');editor.dispose();
});
test('saving is single flight, preserves failed draft and does not reset it on reopen',async()=>{
    const editor=new RequisitesEditor(),pending=deferred();let reads=0,writes=0;
    editor.setAccount('one',transport({read:async()=>{reads++;return stored},save:async draft=>{writes++;if(writes===1)throw new TypeError('offline');await pending.promise;return {...draft,version:draft.expected_version+1,updated_at:stored.updated_at}}}));
    await editor.load();editor.setField('recipient_name','Мои правки');
    assert.equal(await editor.save(),false);assert.equal(editor.getSnapshot().draft.recipient_name,'Мои правки');
    await editor.load();assert.equal(reads,1);assert.equal(editor.getSnapshot().draft.recipient_name,'Мои правки');
    const save=editor.save();assert.equal(await editor.save(),false);editor.setField('recipient_name','Поздно');
    pending.resolve();assert.equal(await save,true);assert.equal(writes,2);assert.equal(editor.getSnapshot().record.recipient_name,'Мои правки');editor.dispose();
});
test('closing aborts the lazy read and ignores its late response',async()=>{
    const editor=new RequisitesEditor(),late=deferred();let signal;
    editor.setAccount('one',transport({read:async s=>{signal=s;return late.promise}}));
    const read=editor.load();editor.cancelRead();assert.equal(signal.aborted,true);
    late.resolve(stored);assert.equal(await read,false);assert.equal(editor.getSnapshot().record,null);assert.equal(editor.getSnapshot().loaded,false);editor.dispose();
});
test('account replacement drops bank data and suppresses a late confirmed write',async()=>{
    const editor=new RequisitesEditor(),late=deferred();let signal;
    editor.setAccount('one',transport({save:async(_,s)=>{signal=s;return late.promise}}));await editor.load();
    const write=editor.save();editor.setAccount('two',transport({read:async()=>null}));assert.equal(signal.aborted,true);
    late.resolve(stored);assert.equal(await write,false);assert.equal(editor.getSnapshot().record,null);assert.equal(editor.getSnapshot().draft.recipient_name,'');editor.dispose();
});

test('stale bank form preserves its draft, blocks repeat writes and requires explicit reload',async()=>{
    const editor=new RequisitesEditor(),writes=[];let reads=0,failReload=true;
    editor.setAccount('one',transport({read:async()=>{
        reads++;if(reads===1)return stored;if(failReload)throw new TypeError('offline');
        return {...stored,version:2,recipient_name:'Свежие данные'};
    },save:async draft=>{
        writes.push(draft);if(writes.length===1)throw new ApiError('Changed',409,null,{code:'requisites_version_conflict'});
        return {...stored,...draft,version:3};
    }}));
    await editor.load();editor.setField('recipient_name','Мой черновик');
    assert.equal(await editor.save(),false);assert.equal(writes[0].expected_version,1);
    assert.equal(editor.getSnapshot().conflict,true);assert.equal(editor.getSnapshot().draft.recipient_name,'Мой черновик');
    await editor.load();assert.equal(reads,1);assert.equal(await editor.save(),false);assert.equal(writes.length,1);
    assert.equal(await editor.reload(),false);assert.equal(editor.getSnapshot().reloadFailed,true);
    assert.equal(editor.getSnapshot().conflict,true);assert.equal(editor.getSnapshot().draft.recipient_name,'Мой черновик');
    failReload=false;assert.equal(await editor.reload(),true);assert.equal(editor.getSnapshot().conflict,false);
    assert.equal(editor.getSnapshot().draft.recipient_name,'Свежие данные');
    editor.setField('recipient_name','Новая правка');assert.equal(await editor.save(),true);assert.equal(writes[1].expected_version,2);
    editor.dispose();
});
test('closing a forced reload retains the loaded draft and ignores a late replacement',async()=>{
    const editor=new RequisitesEditor(),late=deferred();let reads=0;
    editor.setAccount('one',transport({read:async()=>++reads===1?stored:late.promise}));
    await editor.load();editor.setField('recipient_name','Не терять');
    const reload=editor.reload();editor.cancelRead();late.resolve({...stored,version:2});
    assert.equal(await reload,false);assert.equal(editor.getSnapshot().status,'ready');
    assert.equal(editor.getSnapshot().draft.recipient_name,'Не терять');assert.equal(editor.getSnapshot().record.version,1);
    editor.dispose();
});
