import assert from 'node:assert/strict';
import fs from 'node:fs';
import { registerHooks } from 'node:module';
import test from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
const frontend = fileURLToPath(new URL('../../', import.meta.url));
registerHooks({ resolve(specifier, context, next) {
    if (specifier.startsWith('@/')) specifier = pathToFileURL(frontend + specifier.slice(2)).href;
    if (specifier.startsWith('file:') || specifier.startsWith('.')) {
        const url = new URL(specifier, context.parentURL);
        if (!/\.[a-z]+$/i.test(url.pathname) && fs.existsSync(fileURLToPath(url) + '.ts')) return next(url.href + '.ts', context);
    }
    return next(specifier, context);
} });
process.env.NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED = 'true';
process.env.NEXT_PUBLIC_CATALOG_WRITES_ENABLED = 'true';
globalThis.BroadcastChannel = undefined;
const storage = new Map();
globalThis.window = { localStorage: {
    getItem: key => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key),
}, setTimeout, clearTimeout };
globalThis.localStorage = window.localStorage;
const { useAuthStore } = await import('../../store/authStore.ts');
const { runCatalogRequest } = await import('../../store/catalogSession.ts');
const { ApiError } = await import('../api/http.ts');
const user = { id: 1, email: 'owner@example.test', first_name: 'Анна', phone: '', gender: null };

test('disabled catalog and signed-out sessions never call the administrative operation', async () => {
    let calls=0;
    process.env.NEXT_PUBLIC_CATALOG_WRITES_ENABLED='false';
    await assert.rejects(runCatalogRequest(async()=>{calls++}),/отключено/);
    process.env.NEXT_PUBLIC_CATALOG_WRITES_ENABLED='true';
    await assert.rejects(runCatalogRequest(async()=>{calls++}));
    assert.equal(calls,0);
});

test('catalog operation refreshes an expired token through the coordinated session', async t => {
    useAuthStore.getState().setAuth('expired',user);
    const tokens=[];
    t.mock.method(globalThis,'fetch',async url=>{assert.equal(url,'/api/auth/refresh');return Response.json({token:'fresh',user})});
    const value=await runCatalogRequest(async token=>{
        tokens.push(token);if(token==='expired')throw new ApiError('Expired',401);return 42;
    });
    assert.equal(value,42);assert.deepEqual(tokens,['expired','fresh']);
});

test('a delayed model response cannot reach another account or a new login of the same person', async () => {
    for(const replacement of [{...user,id:2},user]) {
        useAuthStore.getState().setAuth('first',user);
        let resolve;
        const waiting=new Promise(ok=>{resolve=ok});
        const request=runCatalogRequest(()=>waiting);
        const rejected=assert.rejects(request,{name:'AbortError'});
        useAuthStore.getState().acceptRemoteLogout(false);
        useAuthStore.getState().setAuth('replacement',replacement);
        resolve({privateModel:42});await rejected;
    }
});
