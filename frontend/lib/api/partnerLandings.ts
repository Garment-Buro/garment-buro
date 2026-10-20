import { ApiError, requestJson, requestReadJson } from './http.ts';
import type {
    OwnLandingPage,
    PartnerLanding,
    PartnerLandingCreatePayload,
    PartnerLandingUpdatePayload,
} from '../partners/types.ts';

export type { OwnLandingPage } from '../partners/types.ts';
import { PageCursorExpiredError } from '../catalog/pagedResource.ts';

export function readOwnLandingPage(value: unknown): OwnLandingPage {
    const page = value as OwnLandingPage | null;
    if (!page || !Array.isArray(page.items) || page.items.length > 24 || !(page.next_cursor === null || typeof page.next_cursor === 'string' && page.next_cursor.length > 0 && page.next_cursor.length <= 512)) throw new Error('Сервер вернул неверный список сообществ.');
    const ids = new Set<number>();
    for (const row of page.items) {
        if (!row || !Number.isSafeInteger(row.id) || row.id <= 0 || ids.has(row.id) || !Number.isSafeInteger(row.version) || row.version <= 0 || typeof row.slug !== 'string' || typeof row.title !== 'string' || !(row.image_url === null || typeof row.image_url === 'string') || !['draft','published','archived'].includes(row.status) || !Number.isSafeInteger(row.product_count) || row.product_count < 0) throw new Error('Сервер вернул неверную карточку сообщества.');
        ids.add(row.id);
    }
    return page;
}
const fields = [
    'title',
    'eyebrow',
    'headline',
    'description',
    'cta_label',
    'cta_href',
    'image_url',
    'template_key',
    'content',
    'product_ids',
    'status',
] as const;
const pick = (value: PartnerLandingUpdatePayload | PartnerLandingCreatePayload) =>
    Object.fromEntries(
        fields.filter((key) => value[key] !== undefined).map((key) => [key, value[key]]),
    );
const idPath = (id: number) => {
    if (!Number.isSafeInteger(id) || id <= 0) throw new RangeError('Invalid landing ID');
    return `/partner/own-landings/${id}`;
};
const privateInit = (token: string, signal?: AbortSignal): RequestInit => ({
    headers: { Authorization: `Bearer ${token}` },
    signal,
    cache: 'no-store',
});
export const getOwnLandings = async (
    token: string, cursor: string | null = null, signal?: AbortSignal,
) => {
    const params = new URLSearchParams({ limit: '24' });
    if (cursor) params.set('cursor', cursor);
    try { return readOwnLandingPage(await requestReadJson<unknown>(`/partner/own-landings?${params}`, privateInit(token, signal))); }
    catch (error) {
        if (error instanceof ApiError && error.status === 422 && error.code === 'invalid_cursor') throw new PageCursorExpiredError();
        throw error;
    }
};
export const getOwnLanding = (token: string, id: number, signal?: AbortSignal) =>
    requestReadJson<PartnerLanding>(idPath(id), privateInit(token, signal));
export const createOwnLanding = (
    token: string,
    value: PartnerLandingCreatePayload,
    signal?: AbortSignal,
) =>
    requestJson<PartnerLanding>('/partner/own-landings', {
        ...privateInit(token, signal),
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...pick(value), slug: value.slug }),
    });
export const updateOwnLanding = (
    token: string,
    id: number,
    value: PartnerLandingUpdatePayload,
    signal?: AbortSignal,
) =>
    requestJson<PartnerLanding>(idPath(id), {
        ...privateInit(token, signal),
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...pick(value), expected_version: value.expected_version }),
    });
