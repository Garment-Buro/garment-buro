import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {registerHooks} from 'node:module';
import test from 'node:test';

registerHooks({resolve(specifier,context,next) {
    if(specifier==='server-only')return next('next/dist/compiled/server-only/empty.js',context);
    if(specifier==='@/lib/server/backend/http')return {url:new URL('../server/backend/http.ts',import.meta.url).href,shortCircuit:true};
    return next(specifier,context);
}});

test('withdrawn landing is read fresh rather than replayed from Next data cache',async t=>{
    const {getPublicPartnerLanding}=await import('./partners.server.ts');
    let status=200;
    const calls=[];
    const server=createServer((request,response)=>{
        calls.push({url:request.url,headers:request.headers});
        response.statusCode=status;response.setHeader('Content-Type','application/json');
        response.end(JSON.stringify(status===200 ? {slug:'my-collection',title:'Published collection'} : {detail:'Unavailable'}));
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const before=process.env.INTERNAL_API_URL;
    process.env.INTERNAL_API_URL=`http://127.0.0.1:${server.address().port}`;
    t.after(async()=>{
        if(before===undefined)delete process.env.INTERNAL_API_URL;else process.env.INTERNAL_API_URL=before;
        server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
    });
    // The external cache is the double; real HTTP and the shipped helper are
    // exercised. A revalidate option would permit replay of the revoked DTO.
    const nativeFetch=globalThis.fetch;
    const stored=new Map();
    t.mock.method(globalThis,'fetch',async (url,init)=>{
        if(init.cache!=='no-store' && stored.has(url))return stored.get(url).clone();
        const response=await nativeFetch(url,init);
        if(init.cache!=='no-store' && response.ok)stored.set(url,response.clone());
        return response;
    });
    assert.equal((await getPublicPartnerLanding('my-collection')).title,'Published collection');
    status=404;assert.equal(await getPublicPartnerLanding('my-collection'),null);
    status=503;await assert.rejects(getPublicPartnerLanding('my-collection'),/status 503/);
    assert.equal(calls.length,3);
    for(const call of calls){
        assert.equal(call.url,'/api/partner/landings/my-collection');
        assert.equal(call.headers.authorization,undefined);assert.equal(call.headers.cookie,undefined);
    }
});
