import assert from 'node:assert/strict';
import test from 'node:test';

import {
    ApiError,
    getPublicApiBaseUrl,
    requestJson,
} from './http.ts';

test('browser API requests always use the application same-origin boundary', () => {
    const previousPublicApiUrl = process.env.NEXT_PUBLIC_API_URL;
    process.env.NEXT_PUBLIC_API_URL = 'https://external-api.example';

    try {
        assert.equal(getPublicApiBaseUrl(), '/api');
    } finally {
        if (previousPublicApiUrl === undefined) {
            delete process.env.NEXT_PUBLIC_API_URL;
        } else {
            process.env.NEXT_PUBLIC_API_URL = previousPublicApiUrl;
        }
    }
});

test('ApiError preserves the response status for feature-level handling', () => {
    const error = new ApiError('Request failed', 422);

    assert.equal(error.name, 'ApiError');
    assert.equal(error.message, 'Request failed');
    assert.equal(error.status, 422);
});

test('requestJson joins relative paths and preserves backend error details', async () => {
    const originalFetch = globalThis.fetch;
    const requestedUrls = [];
    const requestedOptions = [];

    globalThis.fetch = async (url, options) => {
        requestedUrls.push(String(url));
        requestedOptions.push(options);
        if (requestedUrls.length === 1) {
            return Response.json({ ok: true });
        }
        return Response.json({ detail: 'Некорректный запрос' }, { status: 422 });
    };

    try {
        assert.deepEqual(await requestJson('/products'), { ok: true });
        await assert.rejects(
            requestJson('/orders'),
            (error) => error instanceof ApiError
                && error.status === 422
                && error.message === 'Некорректный запрос',
        );
        assert.deepEqual(requestedUrls, ['/api/products', '/api/orders']);
        assert.equal(requestedOptions[0].credentials, 'same-origin');
        assert.equal(requestedOptions[1].credentials, 'same-origin');
    } finally {
        globalThis.fetch = originalFetch;
    }
});
