import { bearerHeaders } from '../api/headers.ts';
import { ApiError, requestReadJson } from '../api/http.ts';
import { PageCursorExpiredError } from '../catalog/pagedResource.ts';
import type { PartnerProfile, PartnerPayout, PartnerDashboard, PartnerRequisites } from './types.ts';

export type AdminPartnerQuery = { query?: string; status?: PartnerProfile['status']; selectable?: boolean; limit?: number; cursor?: string | null };
export type PartnerPayoutQuery = { limit?: number; cursor?: string | null };
export type PrivatePartnerPage<T> = { items: T[]; next_cursor: string | null };
export const partnerReadSearch = (query: AdminPartnerQuery | PartnerPayoutQuery) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) if (value != null && value !== '') params.set(key, String(value));
    params.sort();
    return params.toString();
};
const id = (value: unknown) => Number.isSafeInteger(value) && Number(value) > 0;
const date = (value: unknown) => typeof value === 'string' && Number.isFinite(Date.parse(value));
const nullableDate = (value: unknown) => value == null || date(value);
const money = (value: unknown) => typeof value === 'string' && /^\d+(?:\.\d{1,2})?$/.test(value) && Number.isFinite(Number(value));
function readPage<T extends {id:number}>(value: unknown, valid: (row:T) => boolean, message: string): PrivatePartnerPage<T> {
    const page = value as PrivatePartnerPage<T> | null;
    if (!page || !Array.isArray(page.items) || page.items.length > 100 || !(page.next_cursor === null || typeof page.next_cursor === 'string' && page.next_cursor.length > 0 && page.next_cursor.length <= 2048)) throw new Error(message);
    const ids = new Set<number>();
    for (const row of page.items) {
        if (!row || !id(row.id) || ids.has(row.id) || !valid(row)) throw new Error(message);
        ids.add(row.id);
    }
    return page;
}
export const readAdminPartnerPage = (value: unknown) => readPage<PartnerProfile>(value, row => id(row.user_id) && typeof row.code === 'string' && typeof row.display_name === 'string' && ['active','invited','suspended'].includes(row.status) && Number.isSafeInteger(row.commission_bps) && row.commission_bps >= 0 && row.commission_bps <= 10000 && date(row.created_at), 'Сервер вернул неверный список партнёров.');
export const readPartnerPayoutPage = (value: unknown) => readPage<PartnerPayout>(value, row => money(row.amount) && Number(row.amount) > 0 && row.currency === 'RUB' && ['requested','approved','paid','rejected','canceled'].includes(row.status) && date(row.created_at) && nullableDate(row.reviewed_at) && nullableDate(row.paid_at) && (row.note == null || typeof row.note === 'string'), 'Сервер вернул неверную историю выплат.');
async function requestPage<T>(path: string, token: string, query: AdminPartnerQuery | PartnerPayoutQuery, read: (value:unknown) => T, signal?: AbortSignal): Promise<T> {
    try { return read(await requestReadJson<unknown>(`${path}?${partnerReadSearch(query)}`, {signal, cache:'no-store', headers:bearerHeaders(token)})); }
    catch (error) {
        if (error instanceof ApiError && error.status === 422 && error.code === 'invalid_cursor') throw new PageCursorExpiredError();
        throw error;
    }
}
export const requestAdminPartnerPage = (token: string, query: AdminPartnerQuery, signal?: AbortSignal) => requestPage('/admin/partners', token, query, readAdminPartnerPage, signal);
export const requestPartnerPayoutPage = (token: string, query: PartnerPayoutQuery, signal?: AbortSignal) => requestPage('/partner/payouts', token, query, readPartnerPayoutPage, signal);

export function readPartnerDashboard(value: unknown): PartnerDashboard {
    const row = value as PartnerDashboard | null;
    if (!row || !row.partner || typeof row.has_requisites !== 'boolean'
        || !Number.isSafeInteger(row.orders) || row.orders < 0 || !Number.isSafeInteger(row.visits) || row.visits < 0
        || !money(row.earned) || !money(row.available) || !money(row.paid) || !money(row.conversion_percent) || row.currency !== 'RUB')
        throw new Error('Сервер вернул неверную сводку кабинета.');
    readAdminPartnerPage({items:[row.partner],next_cursor:null});
    return row;
}
export function readPartnerRequisites(value: unknown): PartnerRequisites | null {
    if (value === null) return null;
    const row = value as PartnerRequisites | null;
    if (!row || !['self_employed','sole_proprietor','legal_entity'].includes(row.entity_type)
        || !['recipient_name','tax_id','bank_name','bic','correspondent_account','settlement_account'].every(key => typeof (row as unknown as Record<string,unknown>)[key] === 'string')
        || !(row.kpp == null || typeof row.kpp === 'string') || !date(row.updated_at)
        || !Number.isInteger(row.version) || row.version < 1 || row.version > 2147483647)
        throw new Error('Сервер вернул неверные реквизиты.');
    return row;
}
