import assert from 'node:assert/strict';
import test from 'node:test';
import { PagedResource, PageCursorExpiredError } from './pagedResource.ts';

const deferred = () => {
    let resolve, reject;
    const promise = new Promise((ok, fail) => {resolve=ok; reject=fail});
    return {promise, resolve, reject};
};

test('initial public page renders before hydration and connects without repeating the first fetch', async () => {
    const calls = [];
    const resource = new PagedResource({key:'limit=24', page:{items:[{id:4}], next_cursor:'page-two'}});
    assert.deepEqual(resource.getSnapshot(), {key:'limit=24', status:'ready', items:[{id:4}], nextCursor:'page-two', loadingMore:false, error:null});
    const load = async cursor => {
        calls.push(cursor);
        return {items:[{id:5}], next_cursor:null};
    };
    await resource.start('limit=24', load, {reuseSettled:true});
    assert.deepEqual(calls, []);
    await resource.loadMore();
    assert.deepEqual(calls, ['page-two']);
    assert.deepEqual(resource.getSnapshot().items, [{id:4},{id:5}]);
    await resource.reload();
    assert.deepEqual(calls, ['page-two', null]);
    assert.deepEqual(resource.getSnapshot().items, [{id:5}]);
});

test('server failure stays honest on hydration and only explicit retry fetches products', async () => {
    const resource = new PagedResource({key:'limit=4', error:'unavailable'});
    assert.equal(resource.getSnapshot().status, 'error');
    assert.deepEqual(resource.getSnapshot().items, []);
    let calls = 0;
    await resource.start('limit=4', async () => {calls++; return {items:[{id:8}], next_cursor:null}}, {reuseSettled:true});
    assert.equal(calls, 0);
    assert.equal(resource.getSnapshot().status, 'error');
    await resource.reload();
    assert.equal(calls, 1);
    assert.equal(resource.getSnapshot().status, 'ready');
    assert.deepEqual(resource.getSnapshot().items, [{id:8}]);
});

test('reconnect preserves settled pages but aborts an unfinished next page', async () => {
    const resource = new PagedResource({key:'public', page:{items:[{id:1}], next_cursor:'next'}});
    assert.equal(resource.getSnapshot().status, 'ready');
    const pending = deferred();
    let signal;
    await resource.start('public', (_, value) => {signal=value; return pending.promise}, {reuseSettled:true});
    const more = resource.loadMore();
    resource.dispose();
    await resource.start('public', async () => ({items:[{id:3}], next_cursor:null}), {reuseSettled:true});
    assert.equal(signal.aborted, true);
    assert.equal(resource.getSnapshot().loadingMore, false);
    assert.deepEqual(resource.getSnapshot().items, [{id:1}]);
    assert.equal(resource.getSnapshot().nextCursor, 'next');
    pending.resolve({items:[{id:2}], next_cursor:null});
    await more;
    assert.deepEqual(resource.getSnapshot().items, [{id:1}]);
    await resource.loadMore();
    assert.deepEqual(resource.getSnapshot().items, [{id:1},{id:3}]);
});

test('changed query excludes the initial page and default private consumers do not reuse it', async () => {
    const resource = new PagedResource({key:'old', page:{items:[{id:1}], next_cursor:'old-next'}});
    await resource.start('new', async () => ({items:[{id:2}], next_cursor:null}), {reuseSettled:true});
    assert.deepEqual(resource.getSnapshot().items, [{id:2}]);
    await resource.start('new', async () => ({items:[{id:3}], next_cursor:null}));
    assert.deepEqual(resource.getSnapshot().items, [{id:3}]);
});

test('a changed search cancels the old request and excludes its late response', async () => {
    const old = deferred(), current = deferred();
    const resource = new PagedResource();
    let oldSignal;
    const first = resource.start('old', (_, signal) => {oldSignal=signal; return old.promise});
    const second = resource.start('current', () => current.promise);
    assert.equal(oldSignal.aborted, true);
    old.resolve({items:[{id:1}], next_cursor:null});
    await first;
    assert.equal(resource.getSnapshot().status, 'loading');
    current.resolve({items:[{id:2}], next_cursor:'next'});
    await second;
    assert.deepEqual(resource.getSnapshot().items, [{id:2}]);
    assert.equal(resource.getSnapshot().key, 'current');
});

test('load more is serialized and errors retain the loaded page for retry', async () => {
    const second = deferred();
    const resource = new PagedResource();
    const cursors = [];
    let attempt = 0;
    await resource.start('products', cursor => {
        cursors.push(cursor);
        if(cursor === null) return Promise.resolve({items:[{id:1}], next_cursor:'next'});
        if(attempt++ === 0) return second.promise;
        return Promise.resolve({items:[{id:1}, {id:2}], next_cursor:null});
    });
    const loading = resource.loadMore();
    await resource.loadMore();
    assert.deepEqual(cursors, [null, 'next']);
    second.reject(new Error('Unavailable'));
    await loading;
    assert.deepEqual(resource.getSnapshot().items, [{id:1}]);
    assert.equal(resource.getSnapshot().nextCursor, 'next');
    assert.equal(resource.getSnapshot().loadingMore, false);
    assert.ok(resource.getSnapshot().error);
    await resource.loadMore();
    assert.deepEqual(resource.getSnapshot().items, [{id:1}, {id:2}]);
    assert.equal(resource.getSnapshot().nextCursor, null);
    assert.equal(resource.getSnapshot().error, null);
});

test('disposal aborts work and prevents a pending response from publishing state', async () => {
    const pending = deferred();
    const resource = new PagedResource();
    let notifications = 0;
    const unsubscribe = resource.subscribe(() => notifications++);
    let signal;
    const loading = resource.start('account:one', (_, value) => {signal=value; return pending.promise});
    resource.dispose();
    assert.equal(signal.aborted, true);
    const before = resource.getSnapshot();
    pending.resolve({items:[{id:7}], next_cursor:null});
    await loading;
    assert.equal(resource.getSnapshot(), before);
    assert.equal(notifications, 1);
    unsubscribe();
});

test('an expired cursor retains cards, blocks repeated append and recovers through an explicit first-page reload',async()=>{
    const resource=new PagedResource(),cursors=[];
    let firstReads=0;
    await resource.start('people',async cursor=>{
        cursors.push(cursor);
        if(cursor==='old')throw new PageCursorExpiredError();
        if(cursor==='fresh')return {items:[{id:3}],next_cursor:null};
        return ++firstReads===1?{items:[{id:1}],next_cursor:'old'}:{items:[{id:2}],next_cursor:'fresh'};
    });
    await resource.loadMore();
    assert.equal(resource.getSnapshot().status,'ready');assert.deepEqual(resource.getSnapshot().items,[{id:1}]);
    assert.ok(resource.getSnapshot().error instanceof PageCursorExpiredError);
    await resource.loadMore();assert.deepEqual(cursors,[null,'old']);
    await resource.reload();assert.deepEqual(resource.getSnapshot().items,[{id:2}]);assert.equal(resource.getSnapshot().error,null);
    await resource.loadMore();assert.deepEqual(resource.getSnapshot().items,[{id:2},{id:3}]);assert.deepEqual(cursors,[null,'old',null,'fresh']);
});

test('changing search during cursor recovery cancels reload and excludes its late first page',async()=>{
    const resource=new PagedResource(),pending=deferred();let reloadSignal;
    await resource.start('old',async cursor=>{if(cursor)throw new PageCursorExpiredError();return {items:[{id:1}],next_cursor:'old'}});
    await resource.loadMore();
    await resource.start('old',(_,signal)=>{reloadSignal=signal;return pending.promise},{reuseSettled:true});
    const reload=resource.reload();
    await resource.start('new',async()=>({items:[{id:4}],next_cursor:null}));
    assert.equal(reloadSignal.aborted,true);pending.resolve({items:[{id:2}],next_cursor:'wrong'});await reload;
    assert.equal(resource.getSnapshot().key,'new');assert.deepEqual(resource.getSnapshot().items,[{id:4}]);
});
