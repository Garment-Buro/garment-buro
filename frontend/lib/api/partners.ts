import type {
    PartnerCommission,
    PartnerDashboard,
    PartnerLanding,
    PartnerPayout,
    PartnerCreatePayload,
    PartnerLandingCreatePayload,
    PartnerLandingUpdatePayload,
    PartnerProfile,
} from '@/lib/partners/types';

import { requestJson } from './http';

const authorizedHeaders = (token: string, json = false) => ({
    Authorization: `Bearer ${token}`,
    ...(json ? { 'Content-Type': 'application/json' } : {}),
});

export const getPartnerDashboard = (token: string, signal?: AbortSignal) => (
    requestJson<PartnerDashboard>('/partner/dashboard', {
        headers: authorizedHeaders(token),
        signal,
    })
);

export const getPartnerLandings = (token: string, signal?: AbortSignal) => (
    requestJson<PartnerLanding[]>('/partner/landings', {
        headers: authorizedHeaders(token),
        signal,
    })
);

export const getPartnerCommissions = (token: string, signal?: AbortSignal) => (
    requestJson<PartnerCommission[]>('/partner/commissions', {
        headers: authorizedHeaders(token),
        signal,
    })
);

export const getPartnerPayouts = (token: string, signal?: AbortSignal) => (
    requestJson<PartnerPayout[]>('/partner/payouts', {
        headers: authorizedHeaders(token),
        signal,
    })
);

export const createPartnerPayout = (token: string, amount: string) => (
    requestJson<PartnerPayout>('/partner/payouts', {
        method: 'POST',
        headers: authorizedHeaders(token, true),
        body: JSON.stringify({ amount }),
    })
);

export const registerPartnerVisit = (slug: string) => requestJson<{ attributed: boolean }>(
    `/partner/landings/${encodeURIComponent(slug)}/visits`,
    { method: 'POST' },
);

export const getAdminPartners = (token: string) => requestJson<PartnerProfile[]>(
    '/admin/partners',
    { headers: authorizedHeaders(token) },
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

export const getAdminPartnerLandings = (token: string) => requestJson<PartnerLanding[]>(
    '/admin/partners/landings',
    { headers: authorizedHeaders(token) },
);

export const updateAdminPartnerLanding = (
    token: string,
    landingId: number,
    payload: PartnerLandingUpdatePayload,
) => requestJson<PartnerLanding>(`/admin/partners/landings/${landingId}`, {
    method: 'PATCH',
    headers: authorizedHeaders(token, true),
    body: JSON.stringify(payload),
});
