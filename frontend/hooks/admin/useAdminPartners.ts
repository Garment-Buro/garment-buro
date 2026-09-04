"use client";

import { useCallback, useEffect, useState } from 'react';

import {
    createAdminPartner,
    createAdminPartnerLanding,
    getAdminPartners,
    getAdminPartnerLandings,
    updateAdminPartnerLanding,
} from '@/lib/api/partners';
import type {
    PartnerCreatePayload,
    PartnerLandingCreatePayload,
    PartnerLandingUpdatePayload,
    PartnerLanding,
    PartnerProfile,
} from '@/lib/partners/types';
import { useAuthStore } from '@/store/authStore';

export const useAdminPartners = () => {
    const runAuthenticated = useAuthStore(state => state.runAuthenticated);
    const [partners, setPartners] = useState<PartnerProfile[]>([]);
    const [landings, setLandings] = useState<PartnerLanding[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const reload = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const [partnerResult, landingResult] = await runAuthenticated(token => Promise.all([
                getAdminPartners(token),
                getAdminPartnerLandings(token),
            ]));
            setPartners(partnerResult);
            setLandings(landingResult);
        } catch {
            setError('Не удалось загрузить партнёров. Проверьте доступ администратора.');
        } finally {
            setLoading(false);
        }
    }, [runAuthenticated]);

    useEffect(() => {
        void reload();
    }, [reload]);

    const addPartner = async (payload: PartnerCreatePayload) => {
        const created = await runAuthenticated(token => createAdminPartner(token, payload));
        setPartners(current => [created, ...current]);
        return created;
    };

    const addLanding = async (
        partnerId: number,
        payload: PartnerLandingCreatePayload,
    ) => {
        const landing = await runAuthenticated(token => createAdminPartnerLanding(token, partnerId, payload));
        setLandings(current => [landing, ...current]);
        return landing;
    };

    const updateLanding = async (landingId: number, payload: PartnerLandingUpdatePayload) => {
        const landing = await runAuthenticated(token => updateAdminPartnerLanding(token, landingId, payload));
        setLandings(current => current.map(item => item.id === landing.id ? landing : item));
        return landing;
    };

    return { partners, landings, loading, error, setError, addPartner, addLanding, updateLanding };
};
