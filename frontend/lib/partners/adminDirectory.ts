import { bearerHeaders } from '../api/headers.ts';
import { ApiError, requestReadJson } from '../api/http.ts';
import { PageCursorExpiredError } from '../catalog/pagedResource.ts';
export interface AdminLandingCard {
    id: number;
    version: number;
    title: string;
    slug: string;
    image_url: string | null;
    status: 'draft' | 'published' | 'archived';
    partner_id: number;
    partner_name: string;
    product_count: number;
}
export interface AdminLandingQuery {
    query?: string;
    status?: 'draft' | 'published' | 'archived';
    limit?: number;
    cursor?: string | null;
}
export interface AdminLandingPage {
    items: AdminLandingCard[];
    next_cursor: string | null;
}
export function adminLandingSearch(query: AdminLandingQuery) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query))
        if (value != null && value !== '')
            params.set(key, String(value));
    params.sort();
    return params.toString();
}
export function readAdminLandingPage(value: unknown): AdminLandingPage {
    const page = value as AdminLandingPage | null;
    if (!page || !Array.isArray(page.items) || page.items.length > 100 || !(page.next_cursor === null
        || (typeof page.next_cursor === 'string' && page.next_cursor.length > 0 && page.next_cursor.length <= 2048)))
        throw new Error('Сервер вернул неверную страницу лендингов.');
    const ids = new Set<number>();
    for (const row of page.items) {
        if (!row || !Number.isSafeInteger(row.id) || row.id <= 0 || ids.has(row.id)
            || !Number.isSafeInteger(row.version) || row.version <= 0 || !Number.isSafeInteger(row.partner_id) || row.partner_id <= 0
            || !Number.isSafeInteger(row.product_count) || row.product_count < 0 || typeof row.title !== 'string'
            || typeof row.slug !== 'string' || typeof row.partner_name !== 'string'
            || !(row.image_url === null || typeof row.image_url === 'string')
            || !['draft', 'published', 'archived'].includes(row.status))
            throw new Error('Сервер вернул неверный лендинг.');
        ids.add(row.id);
    }
    return page;
}
export async function requestAdminLandingPage(path: string, query: AdminLandingQuery, signal: AbortSignal, token?: string) {
    try {
        return readAdminLandingPage(await requestReadJson<unknown>(`${path}?${adminLandingSearch(query)}`, { signal, cache: 'no-store', headers: bearerHeaders(token) }));
    }
    catch (error) {
        if (error instanceof ApiError && error.status === 422 && error.code === 'invalid_cursor')
            throw new PageCursorExpiredError();
        throw error;
    }
}
