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
globalThis.BroadcastChannel = undefined;
const storage = new Map();
globalThis.window = { localStorage: {
    getItem: key => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key),
}, setTimeout, clearTimeout };
globalThis.localStorage = window.localStorage;
const { useAuthStore } = await import('../../store/authStore.ts');
const { isCustomerSessionCurrent, runForCustomer } = await import('../../hooks/catalog/customerSession.ts');
const { ApiError } = await import('../api/http.ts');
const { useCheckoutDetailsStore } = await import('../../store/checkoutDetailsStore.ts');
const { authSessionChannel } = await import('./sessionChannel.ts');
const user = { id: 1, email: 'owner@example.test', first_name: 'Анна', phone: '', gender: null };
const key = () => {
    const state = useAuthStore.getState();
    return `${state.user.id}:${state.accountEpoch ?? state.sessionGeneration ?? 'session'}`;
};

test('an expired access token can refresh and retry without changing the customer editing identity', async () => {
    useAuthStore.getState().setAuth('expired', user);
    const editingKey = key();
    const previousFetch = globalThis.fetch;
    globalThis.fetch = async url => {
        assert.equal(url, '/api/auth/refresh');
        return Response.json({ token: 'refreshed', user });
    };
    try {
        const saved = await runForCustomer(1, async token => {
            if (token === 'expired') throw new ApiError('Expired', 401);
            assert.equal(token, 'refreshed');
            return { id: 42, version: 2 };
        }, editingKey);
        assert.equal(saved.version, 2);
        assert.equal(key(), editingKey);
        assert.equal(isCustomerSessionCurrent(1, editingKey), true);
    } finally { globalThis.fetch = previousFetch; }
});

test('profile and remote token updates preserve editing identity; logout and account changes revoke it', async () => {
    useAuthStore.getState().setAuth('first', user);
    const editingKey = key();
    useAuthStore.getState().updateUser({ ...user, first_name: 'Вера' });
    assert.equal(isCustomerSessionCurrent(1, editingKey), true);
    useAuthStore.getState().acceptRemoteSession({ token: 'remote', user }, 'remote-token-generation');
    assert.equal(key(), editingKey);
    useAuthStore.getState().acceptRemoteLogout(false);
    assert.equal(isCustomerSessionCurrent(1, editingKey), false);
    useAuthStore.getState().setAuth('login-again', user);
    assert.notEqual(key(), editingKey);
    const newKey = key();
    useAuthStore.getState().acceptRemoteSession({ token: 'another', user: { ...user, id: 2 } }, 'another-generation');
    assert.equal(isCustomerSessionCurrent(1, newKey), false);
});

test('checkout drafts survive token refresh but are cleared before another customer or guest can read them', () => {
    useAuthStore.getState().setAuth('customer-a', user);
    const contact = { name: 'Private buyer', phone: '+79001234567', email: 'private@example.test' };
    useCheckoutDetailsStore.getState().setContacts(contact, contact, true);
    useCheckoutDetailsStore.getState().setCourier({ city: 'Private city', street: 'Private street', house: '7', apartment: '', entrance: '', floor: '', intercom: '', comment: '' });
    useAuthStore.getState().acceptRemoteSession({ token: 'refreshed-a', user }, 'refreshed-a-generation');
    assert.equal(useCheckoutDetailsStore.getState().buyer.name, 'Private buyer');
    useAuthStore.getState().acceptRemoteSession({ token: 'customer-b', user: { ...user, id: 2 } }, 'customer-b-generation');
    assert.equal(useCheckoutDetailsStore.getState().buyer.name, '');
    assert.equal(useCheckoutDetailsStore.getState().courier.city, '');
    useCheckoutDetailsStore.getState().setContacts(contact, contact, true);
    useAuthStore.getState().acceptRemoteLogout(false);
    assert.equal(useCheckoutDetailsStore.getState().buyer.email, '');
});

const deferred = () => {
    let resolve, reject;
    const promise = new Promise((ok, fail) => { resolve = ok; reject = fail; });
    return { promise, resolve, reject };
};

test('a same-user login in another tab revokes writes from the previous login lifetime', async () => {
    useAuthStore.getState().setAuth('old-login', user);
    const editingKey = key(), response = deferred();
    const writing = runForCustomer(1, () => response.promise, editingKey);
    const rejected = assert.rejects(writing, { name: 'AbortError' });
    useAuthStore.getState().acceptRemoteSession(
        { token: 'new-login', user: { ...user, first_name: 'Новый вход' } },
        'new-login-generation', 'shared-new-login-lifetime',
    );
    response.resolve({ ...user, first_name: 'Старый ответ' });
    await rejected;
    assert.equal(isCustomerSessionCurrent(1, editingKey), false);
    assert.equal(useAuthStore.getState().user.first_name, 'Новый вход');
});

test('a remote token rotation keeps the shared login lifetime and pending writes', async () => {
    useAuthStore.getState().setAuth('old-token', user);
    const editingKey = key(), epoch = useAuthStore.getState().accountEpoch;
    const response = deferred();
    const writing = runForCustomer(1, () => response.promise, editingKey);
    useAuthStore.getState().acceptRemoteSession({ token: 'fresh-token', user }, 'rotation', epoch);
    response.resolve({ saved: true });
    assert.deepEqual(await writing, { saved: true });
    assert.equal(key(), editingKey);
});

test('a late refresh cannot replace the account that signed in while it was pending', async () => {
    useAuthStore.getState().setAuth('expired-a', user);
    const editingKey = key(), started = deferred(), response = deferred();
    const previousFetch = globalThis.fetch;
    globalThis.fetch = async url => {
        assert.equal(url, '/api/auth/refresh');
        started.resolve();
        return response.promise;
    };
    try {
        const saving = runForCustomer(1, async () => { throw new ApiError('Expired', 401); }, editingKey);
        const rejected = assert.rejects(saving, { name: 'AbortError' });
        await started.promise;
        useAuthStore.getState().setAuth('account-b', { ...user, id: 2, first_name: 'Борис' });
        const newKey = key();
        response.resolve(Response.json({ token: 'late-a', user }));
        await rejected;
        assert.equal(useAuthStore.getState().user.id, 2);
        assert.equal(useAuthStore.getState().token, 'account-b');
        assert.equal(key(), newKey);
    } finally { globalThis.fetch = previousFetch; }
});

test('a refused stale refresh cannot log out a newer login of the same customer', async () => {
    useAuthStore.getState().setAuth('expired-old-login', user);
    const editingKey = key(), started = deferred(), response = deferred();
    const previousFetch = globalThis.fetch;
    globalThis.fetch = async () => { started.resolve(); return response.promise; };
    try {
        const saving = runForCustomer(1, async () => { throw new ApiError('Expired', 401); }, editingKey);
        const rejected = assert.rejects(saving, { name: 'AbortError' });
        await started.promise;
        useAuthStore.getState().setAuth('same-customer-new-login', user);
        const newKey = key();
        response.resolve(Response.json({ detail: 'Expired' }, { status: 401 }));
        await rejected;
        assert.equal(useAuthStore.getState().isAuthenticated, true);
        assert.equal(useAuthStore.getState().token, 'same-customer-new-login');
        assert.equal(key(), newKey);
    } finally { globalThis.fetch = previousFetch; }
});

test('session restoration cannot resurrect an account after an explicit logout', async () => {
    useAuthStore.getState().acceptRemoteLogout(false);
    authSessionChannel.publishLogout(false);
    const started = deferred(), response = deferred(), previousFetch = globalThis.fetch;
    globalThis.fetch = async () => { started.resolve(); return response.promise; };
    try {
        const restoring = useAuthStore.getState().initializeSession();
        await started.promise;
        useAuthStore.getState().acceptRemoteLogout(false);
        response.resolve(Response.json({ token: 'stale-restore', user }));
        await restoring;
        assert.equal(useAuthStore.getState().user, null);
        assert.equal(useAuthStore.getState().token, null);
        assert.equal(useAuthStore.getState().isAuthenticated, false);
    } finally { globalThis.fetch = previousFetch; }
});

test('an old authenticated operation cannot retry its write with a different account token', async () => {
    useAuthStore.getState().setAuth('account-a', user);
    const response = deferred();
    let attempts = 0;
    const writing = useAuthStore.getState().runAuthenticated(async token => {
        attempts++;
        if (attempts > 1) assert.fail('old operation retried with ' + token);
        return response.promise;
    });
    const rejected = assert.rejects(writing, { name: 'AbortError' });
    useAuthStore.getState().setAuth('account-b', { ...user, id: 2 });
    response.reject(new ApiError('Expired', 401));
    await rejected;
    assert.equal(attempts, 1);
    assert.equal(useAuthStore.getState().user.id, 2);
});

test('a late logout response cannot clear a new login or publish another logout', async () => {
    useAuthStore.getState().setAuth('account-a', user);
    const started = deferred(), response = deferred(), previousFetch = globalThis.fetch;
    globalThis.fetch = async url => {
        assert.equal(url, '/api/auth/logout');
        started.resolve();
        return response.promise;
    };
    try {
        const loggingOut = useAuthStore.getState().logout();
        await started.promise;
        useAuthStore.getState().setAuth('account-b', { ...user, id: 2 });
        const newKey = key(), generation = authSessionChannel.getSharedGeneration();
        response.resolve(new Response(null, { status: 204 }));
        await loggingOut;
        assert.equal(useAuthStore.getState().user?.id, 2);
        assert.equal(useAuthStore.getState().token, 'account-b');
        assert.equal(key(), newKey);
        assert.equal(authSessionChannel.getSharedGeneration(), generation);
        assert.equal(useAuthStore.getState().logoutPending, false);
    } finally { globalThis.fetch = previousFetch; }
});

test('a failed logout cannot mark a later login as needing logout recovery', async () => {
    useAuthStore.getState().setAuth('account-a', user);
    const started = deferred(), response = deferred(), previousFetch = globalThis.fetch;
    globalThis.fetch = async () => { started.resolve(); return response.promise; };
    try {
        const loggingOut = useAuthStore.getState().logout();
        await started.promise;
        useAuthStore.getState().setAuth('account-b', { ...user, id: 2 });
        response.reject(new TypeError('Offline'));
        await loggingOut;
        assert.equal(useAuthStore.getState().logoutPending, false);
        assert.equal(useAuthStore.getState().isAuthenticated, true);
        assert.equal(useAuthStore.getState().token, 'account-b');
    } finally { globalThis.fetch = previousFetch; }
});

test('a successful old operation is discarded when a new session owns the UI', async () => {
    useAuthStore.getState().setAuth('old-login', user);
    const response = deferred();
    const saving = useAuthStore.getState().runAuthenticated(() => response.promise);
    const rejected = assert.rejects(saving, { name: 'AbortError' });
    useAuthStore.getState().setAuth('new-login', user);
    response.resolve({ ...user, first_name: 'Старый ответ' });
    await rejected;
    assert.equal(useAuthStore.getState().token, 'new-login');
    assert.equal(useAuthStore.getState().user.first_name, 'Анна');
});

test('a failed stale restoration cannot mark an already authenticated session as pending', async () => {
    useAuthStore.getState().acceptRemoteLogout(false);
    authSessionChannel.publishLogout(false);
    const started = deferred(), response = deferred(), previousFetch = globalThis.fetch;
    globalThis.fetch = async () => { started.resolve(); return response.promise; };
    try {
        const restoring = useAuthStore.getState().initializeSession();
        await started.promise;
        useAuthStore.getState().setAuth('new-login', user);
        response.reject(new TypeError('Offline'));
        await restoring;
        assert.equal(useAuthStore.getState().sessionRestorePending, false);
        assert.equal(useAuthStore.getState().isAuthenticated, true);
        assert.equal(useAuthStore.getState().token, 'new-login');
    } finally { globalThis.fetch = previousFetch; }
});

test('a new OTP login waits for an old refresh before it installs the new session', async () => {
    useAuthStore.getState().setAuth('expired-a', user);
    const started = deferred(), response = deferred(), previousFetch = globalThis.fetch;
    const secondUser = { ...user, id: 2, first_name: 'Борис' };
    let cookieOwner = 1;
    globalThis.fetch = async url => {
        if (url === '/api/auth/refresh') {
            started.resolve();
            await response.promise;
            cookieOwner = 1;
            return Response.json({ token: 'fresh-a', user });
        }
        assert.equal(url, '/api/auth/email/verify');
        cookieOwner = 2;
        return Response.json({ token: 'account-b', user: secondUser });
    };
    try {
        const saving = runForCustomer(1, async token => {
            if (token === 'expired-a') throw new ApiError('Expired', 401);
            return { saved: true };
        }, key()).catch(error => { assert.equal(error.name, 'AbortError'); });
        await started.promise;
        const login = useAuthStore.getState().authenticate('b@example.test', '1234');
        response.resolve();
        await Promise.all([saving, login]);
        assert.equal(useAuthStore.getState().user.id, 2);
        assert.equal(useAuthStore.getState().token, 'account-b');
        assert.equal(cookieOwner, 2);
    } finally { globalThis.fetch = previousFetch; }
});

test('OTP login waits for an old logout cookie before starting the new session', async () => {
    useAuthStore.getState().setAuth('account-a', user);
    const started = deferred(), response = deferred(), previousFetch = globalThis.fetch;
    let cookieOwner = 1;
    globalThis.fetch = async url => {
        if (url === '/api/auth/logout') {
            started.resolve();
            await response.promise;
            cookieOwner = null;
            return Response.json({ logged_out: true });
        }
        assert.equal(url, '/api/auth/email/verify');
        cookieOwner = 2;
        return Response.json({ token: 'account-b', user: { ...user, id: 2 } });
    };
    try {
        const loggingOut = useAuthStore.getState().logout();
        await started.promise;
        const login = useAuthStore.getState().authenticate('b@example.test', '1234');
        response.resolve();
        await Promise.all([loggingOut, login]);
        assert.equal(useAuthStore.getState().user.id, 2);
        assert.equal(useAuthStore.getState().logoutPending, false);
        assert.equal(cookieOwner, 2);
    } finally { globalThis.fetch = previousFetch; }
});

test('a later explicit logout cancels a login still waiting for cookie coordination', async () => {
    useAuthStore.getState().setAuth('account-a', user);
    const held = deferred(), release = deferred();
    const blocker = navigator.locks.request('garment-buro-auth-refresh', async () => {
        held.resolve(); await release.promise;
    });
    await held.promise;
    const previousFetch = globalThis.fetch, requests = [];
    globalThis.fetch = async url => {
        requests.push(url);
        return url.endsWith('/verify')
            ? Response.json({ token: 'account-b', user: { ...user, id: 2 } })
            : Response.json({ logged_out: true });
    };
    try {
        const login = useAuthStore.getState().authenticate('b@example.test', '1234');
        const rejected = assert.rejects(login, { name: 'AbortError' });
        const logout = useAuthStore.getState().logout();
        release.resolve();
        await Promise.all([blocker, rejected, logout]);
        assert.deepEqual(requests, ['/api/auth/logout']);
        assert.equal(useAuthStore.getState().isAuthenticated, false);
        assert.equal(useAuthStore.getState().logoutPending, false);
    } finally { release.resolve(); globalThis.fetch = previousFetch; }
});

test('a fresh tab restores the existing shared login lifetime rather than creating a new login', async () => {
    useAuthStore.getState().acceptRemoteLogout(false);
    authSessionChannel.publishLogout(false);
    // A fresh tab has shared opaque markers, but no prior BroadcastChannel message.
    storage.set('gb-auth-session-generation', 'existing-tab-generation');
    storage.set('gb-auth-account-epoch', 'existing-login-lifetime');
    const previousFetch = globalThis.fetch;
    globalThis.fetch = async url => {
        assert.equal(url, '/api/auth/refresh');
        return Response.json({ token: 'restored', user });
    };
    try {
        await useAuthStore.getState().initializeSession();
        assert.equal(useAuthStore.getState().accountEpoch, 'existing-login-lifetime');
        assert.equal(useAuthStore.getState().user.id, 1);
    } finally { globalThis.fetch = previousFetch; }
});

test('a cross-tab logout revokes old writes before its broadcast reaches the local store', async () => {
    useAuthStore.getState().setAuth('account-a', user);
    const response = deferred();
    const writing = useAuthStore.getState().runAuthenticated(() => response.promise);
    const rejected = assert.rejects(writing, { name: 'AbortError' });
    authSessionChannel.publishLogout(true);
    const logoutGeneration = authSessionChannel.getSharedGeneration();
    response.resolve({ ...user, first_name: 'Старый ответ' });
    await rejected;
    assert.throws(() => useAuthStore.getState().updateUser({ ...user, first_name: 'Старый ответ' }), { name: 'AbortError' });
    assert.equal(authSessionChannel.getSharedAccountEpoch(), null);
    assert.equal(authSessionChannel.getSharedGeneration(), logoutGeneration);
});

test('a guest verification cannot publish a login after a later cross-tab logout intent', async () => {
    useAuthStore.getState().acceptRemoteLogout(false);
    authSessionChannel.publishLogout(false);
    const started = deferred(), response = deferred(), previousFetch = globalThis.fetch;
    globalThis.fetch = async () => { started.resolve(); return response.promise; };
    try {
        const login = useAuthStore.getState().authenticate('owner@example.test', '1234');
        const rejected = assert.rejects(login, { name: 'AbortError' });
        await started.promise;
        authSessionChannel.publishLogout(true);
        const logoutGeneration = authSessionChannel.getSharedGeneration();
        response.resolve(Response.json({ token: 'late-login', user }));
        await rejected;
        assert.equal(useAuthStore.getState().isAuthenticated, false);
        assert.equal(authSessionChannel.getSharedGeneration(), logoutGeneration);
    } finally { response.resolve(Response.json({ token: 'late-login', user })); globalThis.fetch = previousFetch; }
});

test('a fresh tab cannot restore a login after a later cross-tab logout intent', async () => {
    useAuthStore.getState().acceptRemoteLogout(false);
    authSessionChannel.publishLogout(false);
    storage.set('gb-auth-session-generation', 'existing-generation-without-message');
    storage.set('gb-auth-account-epoch', 'existing-login-lifetime');
    const started = deferred(), response = deferred(), previousFetch = globalThis.fetch;
    globalThis.fetch = async () => { started.resolve(); return response.promise; };
    try {
        const restoring = useAuthStore.getState().initializeSession();
        await started.promise;
        authSessionChannel.publishLogout(true);
        const logoutGeneration = authSessionChannel.getSharedGeneration();
        response.resolve(Response.json({ token: 'late-restore', user }));
        await restoring;
        assert.equal(useAuthStore.getState().isAuthenticated, false);
        assert.equal(authSessionChannel.getSharedAccountEpoch(), null);
        assert.equal(authSessionChannel.getSharedGeneration(), logoutGeneration);
    } finally { response.resolve(Response.json({ token: 'late-restore', user })); globalThis.fetch = previousFetch; }
});
