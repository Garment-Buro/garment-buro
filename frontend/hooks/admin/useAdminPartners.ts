"use client";

import { useCallback, useEffect, useState } from 'react';

import {
    createAdminPartner,
    createAdminPartnerLanding,
    getAdminPartners,
} from '@/lib/api/partners';
import type {
    PartnerCreatePayload,
    PartnerLandingCreatePayload,
    PartnerProfile,
} from '@/lib/partners/types';
import { useAuthStore } from '@/store/authStore';

export const useAdminPartners = () => {
    const runAuthenticated = useAuthStore(state => state.runAuthenticated);
    const [partners, setPartners] = useState<PartnerProfile[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const reload = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const result = await runAuthenticated(token => getAdminPartners(token));
            setPartners(result);
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
    ) => runAuthenticated(token => createAdminPartnerLanding(token, partnerId, payload));

    return { partners, loading, error, setError, addPartner, addLanding };
};
