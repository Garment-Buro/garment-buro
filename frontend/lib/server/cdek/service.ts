import type { CdekRequestBody, CdekServiceResponse } from './types.ts';
import { normalizeCdekOffices, normalizeCdekTariffs } from './normalize';
import { toCdekOfficeParams } from './utils.ts';

const CDEK_API_BASE = process.env.CDEK_API_URL || 'https://api.cdek.ru/v2';
const CDEK_CLIENT_ID = process.env.CDEK_CLIENT_ID || '';
const CDEK_CLIENT_SECRET = process.env.CDEK_CLIENT_SECRET || '';
const CDEK_WIDGET_VERSION = '3.11.1';
const CDEK_CACHE_TTL_MS = 4 * 60 * 60 * 1000;

export const CDEK_JSON_HEADERS = {
    'Content-Type': 'application/json',
    'X-Service-Version': CDEK_WIDGET_VERSION,
};

let cachedToken: string | null = null;
let tokenExpiry = 0;

const responseCache = new Map<string, CdekServiceResponse & { expiry: number }>();

const getCachedResponse = (key: string): CdekServiceResponse | null => {
    const cached = responseCache.get(key);
    if (!cached || Date.now() >= cached.expiry) return null;
    return { data: cached.data, status: cached.status };
};

const cacheResponse = (key: string, response: CdekServiceResponse) => {
    responseCache.set(key, {
        ...response,
        expiry: Date.now() + CDEK_CACHE_TTL_MS,
    });
};

const getCdekToken = async (): Promise<string> => {
    const now = Date.now();

    if (!CDEK_CLIENT_ID || !CDEK_CLIENT_SECRET) {
        throw new Error('CDEK credentials are not configured');
    }

    if (cachedToken && now < tokenExpiry - 60_000) return cachedToken;

    const response = await fetch(`${CDEK_API_BASE}/oauth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
            grant_type: 'client_credentials',
            client_id: CDEK_CLIENT_ID,
            client_secret: CDEK_CLIENT_SECRET,
        }),
        cache: 'no-store',
    });

    if (!response.ok) throw new Error('Failed to authenticate with CDEK API');

    const data = await response.json() as { access_token?: string; expires_in?: number };
    if (!data.access_token) throw new Error('No access token in CDEK response');

    cachedToken = data.access_token;
    tokenExpiry = now + (data.expires_in ?? 0) * 1000;
    return data.access_token;
};

const requestCdek = async (
    cacheKey: string,
    path: string,
    init: RequestInit = {},
    normalize: (value: unknown) => unknown,
): Promise<CdekServiceResponse> => {
    const cached = getCachedResponse(cacheKey);
    if (cached) return cached;

    const token = await getCdekToken();
    const response = await fetch(`${CDEK_API_BASE}${path}`, {
        ...init,
        headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'application/json',
            'X-App-Name': 'widget_pvz',
            'X-App-Version': CDEK_WIDGET_VERSION,
            ...init.headers,
        },
    });
    const payload = await response.json().catch(() => null);
    const result = {
        data: response.ok
            ? normalize(payload)
            : { message: 'CDEK request failed' },
        status: response.status,
    };

    if (response.ok) cacheResponse(cacheKey, result);
    return result;
};

export const getCdekOffices = (params: URLSearchParams, source: 'get' | 'post' = 'get') => (
    requestCdek(
        `${source}_offices_${params.toString()}`,
        `/deliverypoints?${params.toString()}`,
        {},
        normalizeCdekOffices,
    )
);

export const getCdekOfficesFromBody = (body: CdekRequestBody) => (
    getCdekOffices(toCdekOfficeParams(Object.entries(body)), 'post')
);

export const calculateCdekTariffs = (body: CdekRequestBody) => requestCdek(
    `calculate_${JSON.stringify(body)}`,
    '/calculator/tarifflist',
    {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    },
    normalizeCdekTariffs,
);
