import type {
    PartnerLanding,
    PartnerPayout,
    PartnerRequisitesWrite,
    PartnerCreatePayload,
    PartnerLandingCreatePayload,
    PartnerLandingUpdatePayload,
    PartnerProfile,
} from '@/lib/partners/types';

import { requestJson, requestReadJson } from './http';
import { readPartnerDashboard, readPartnerRequisites } from '../partners/privateReads';

const authorizedHeaders = (token: string, json = false) => ({
    Authorization: `Bearer ${token}`,
    ...(json ? { 'Content-Type': 'application/json' } : {}),
});

export const getPartnerDashboard = async (token: string, signal?: AbortSignal) =>
    readPartnerDashboard(await requestReadJson<unknown>('/partner/dashboard', {
        headers: authorizedHeaders(token), signal, cache: 'no-store',
    }));

export const getPartnerRequisites = async (token: string, signal?: AbortSignal) =>
    readPartnerRequisites(await requestReadJson<unknown>('/partner/requisites', {
        headers: authorizedHeaders(token), signal, cache: 'no-store',
    }));

export const updatePartnerRequisites = async (
    token: string, payload: PartnerRequisitesWrite, signal?: AbortSignal,
) => {
    const saved = readPartnerRequisites(await requestJson<unknown>('/partner/requisites', {
        method: 'PUT', headers: authorizedHeaders(token, true), body: JSON.stringify(payload), signal,
    }));
    if (!saved) throw new Error('Сервер не подтвердил реквизиты.');
    return saved;
};

export const createPartnerPayout = (token: string, amount: string, signal?: AbortSignal) => (
    requestJson<PartnerPayout>('/partner/payouts', {
        method: 'POST',
        headers: authorizedHeaders(token, true),
        body: JSON.stringify({ amount }),
        signal,
    })
);

export const registerPartnerVisit = (slug: string) => requestJson<{ attributed: boolean }>(
    `/partner/landings/${encodeURIComponent(slug)}/visits`,
    { method: 'POST' },
);

export const createAdminPartner = (token: string, payload: PartnerCreatePayload) => (
    requestJson<PartnerProfile>('/admin/partners', {
        method: 'POST',
        headers: authorizedHeaders(token, true),
        body: JSON.stringify(payload),
    })
);

export const createAdminPartnerLanding = (
    token: string,
    partnerId: number,
    payload: PartnerLandingCreatePayload,
) => requestJson<PartnerLanding>(`/admin/partners/${partnerId}/landings`, {
    method: 'POST',
    headers: authorizedHeaders(token, true),
    body: JSON.stringify(payload),
});

export const updateAdminPartnerLanding = (
    token: string,
    landingId: number,
    payload: PartnerLandingUpdatePayload,
) => requestJson<PartnerLanding>(`/admin/partners/landings/${landingId}`, {
    method: 'PATCH',
    headers: authorizedHeaders(token, true),
    body: JSON.stringify(payload),
});
