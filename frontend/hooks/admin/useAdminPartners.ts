'use client';
import { useState } from 'react';
import { useCustomerAccount, runForCustomer } from '@/hooks/catalog/customerSession';
import { createAdminPartner, createAdminPartnerLanding, updateAdminPartnerLanding } from '@/lib/api/partners';
import type { PartnerCreatePayload, PartnerLandingCreatePayload, PartnerLandingUpdatePayload } from '@/lib/partners/types';
export const useAdminPartners = () => {
    const account = useCustomerAccount();
    const [error, setError] = useState('');
    const [landingsRevision, setLandingsRevision] = useState(0);
    const [partnersRevision, setPartnersRevision] = useState(0);
    const run = <T,>(operation: (token: string) => Promise<T>) => {
        if (!account.userId)
            return Promise.reject<T>(new Error('Войдите в аккаунт для управления партнёрами.'));
        return runForCustomer(account.userId, operation, account.key);
    };
    const addPartner = async (payload: PartnerCreatePayload) => {
        const created = await run(token => createAdminPartner(token, payload));
        setPartnersRevision(value => value + 1);
        return created;
    };
    const addLanding = async (partnerId: number, payload: PartnerLandingCreatePayload) => {
        const landing = await run(token => createAdminPartnerLanding(token, partnerId, payload));
        setLandingsRevision(value => value + 1);
        return landing;
    };
    const updateLanding = async (id: number, payload: PartnerLandingUpdatePayload) => {
        const landing = await run(token => updateAdminPartnerLanding(token, id, payload));
        setLandingsRevision(value => value + 1);
        return landing;
    };
    return { error, setError, addPartner, addLanding, updateLanding, landingsRevision, partnersRevision };
};
