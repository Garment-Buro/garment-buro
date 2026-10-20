import assert from 'node:assert/strict';
import test from 'node:test';
import {getStorefrontProducts} from './storefront.ts';
import {getCommunities} from './communities.ts';
import {getPeople} from './people.ts';

for(const [name,read] of [['clothing',getStorefrontProducts],['communities',getCommunities],['people',getPeople]]) {
    test(`${name} distinguishes a rejected public cursor from other 422 errors`,async t=>{
        let detail={code:'invalid_cursor',message:'The list changed'};
        t.mock.method(globalThis,'fetch',async()=>Response.json({detail},{status:422}));
        await assert.rejects(read({cursor:'old'}),{name:'PageCursorExpiredError'});
        detail=[{loc:['query','limit'],msg:'Must be at most 100'}];
        await assert.rejects(read({}),error=>error.name==='ApiError'&&error.status===422&&error.code===null);
    });
}
