"use client";

import { useCallback, useEffect, useMemo, useState } from 'react';

import { ApiError } from '@/lib/api/http';
import {
    createPartnerPayout,
    getPartnerDashboard,
    getPartnerLandings,
    getPartnerPayouts,
    getPartnerRequisites,
    updatePartnerRequisites,
} from '@/lib/api/partners';
import type {
    PartnerDashboard,
    PartnerEntityType,
    PartnerLanding,
    PartnerPayout,
    PartnerRequisites,
    PartnerRequisitesPayload,
} from '@/lib/partners/types';
import { useAuthStore } from '@/store/authStore';

const EMPTY_REQUISITES: PartnerRequisitesPayload = {
    entity_type: 'self_employed',
    recipient_name: '',
    tax_id: '',
    kpp: null,
    bank_name: '',
    bic: '',
    correspondent_account: '',
    settlement_account: '',
};

const asRequisitesPayload = (
    requisites: PartnerRequisites | null,
): PartnerRequisitesPayload => requisites ? {
    entity_type: requisites.entity_type,
    recipient_name: requisites.recipient_name,
    tax_id: requisites.tax_id,
    kpp: requisites.kpp ?? null,
    bank_name: requisites.bank_name,
    bic: requisites.bic,
    correspondent_account: requisites.correspondent_account,
    settlement_account: requisites.settlement_account,
} : { ...EMPTY_REQUISITES };

export const usePartnerCabinet = () => {
    const { user, runAuthenticated, logout } = useAuthStore();
    const [dashboard, setDashboard] = useState<PartnerDashboard | null>(null);
    const [landings, setLandings] = useState<PartnerLanding[]>([]);
    const [payouts, setPayouts] = useState<PartnerPayout[]>([]);
    const [requisites, setRequisites] = useState<PartnerRequisites | null>(null);
    const [requisitesDraft, setRequisitesDraft] = useState<PartnerRequisitesPayload>(
        EMPTY_REQUISITES,
    );
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [payoutAmount, setPayoutAmount] = useState('');
    const [payoutPending, setPayoutPending] = useState(false);
    const [requisitesPending, setRequisitesPending] = useState(false);

    const load = useCallback(async (signal?: AbortSignal) => {
        setError('');
        try {
            const result = await runAuthenticated(token => Promise.all([
                getPartnerDashboard(token, signal),
                getPartnerLandings(token, signal),
                getPartnerPayouts(token, signal),
                getPartnerRequisites(token, signal),
            ]));
            setDashboard(result[0]);
            setLandings(result[1]);
            setPayouts(result[2]);
            setRequisites(result[3]);
            setRequisitesDraft(asRequisitesPayload(result[3]));
        } catch (loadError) {
            if (signal?.aborted) return;
            setError(loadError instanceof ApiError && loadError.status === 403
                ? 'Для этого аккаунта не открыт партнёрский доступ.'
                : 'Не удалось загрузить кабинет. Попробуйте ещё раз.');
        } finally {
            if (!signal?.aborted) setLoading(false);
        }
    }, [runAuthenticated]);

    useEffect(() => {
        const controller = new AbortController();
        void load(controller.signal);
        return () => controller.abort();
    }, [load]);

    const requestPayout = async () => {
        if (!payoutAmount || Number(payoutAmount) <= 0 || !requisites) return false;
        setPayoutPending(true);
        setError('');
        setNotice('');
        try {
            await runAuthenticated(token => createPartnerPayout(token, payoutAmount));
            setPayoutAmount('');
            await load();
            setNotice('Заявка на выплату отправлена. Мы покажем новый статус в истории.');
            return true;
        } catch (requestError) {
            if (requestError instanceof ApiError && requestError.message.includes('requisites')) {
                setError('Сначала сохраните реквизиты для выплаты.');
            } else {
                setError(requestError instanceof ApiError && requestError.status === 409
                    ? 'Сумма больше доступного баланса.'
                    : 'Не удалось создать заявку на выплату.');
            }
            return false;
        } finally {
            setPayoutPending(false);
        }
    };

    const saveRequisites = async () => {
        setRequisitesPending(true);
        setError('');
        setNotice('');
        try {
            const saved = await runAuthenticated(token => updatePartnerRequisites(
                token,
                {
                    ...requisitesDraft,
                    kpp: requisitesDraft.entity_type === 'legal_entity'
                        ? requisitesDraft.kpp
                        : null,
                },
            ));
            setRequisites(saved);
            setRequisitesDraft(asRequisitesPayload(saved));
            setNotice('Реквизиты сохранены. Теперь можно отправить заявку на выплату.');
            return true;
        } catch {
            setError('Не удалось сохранить реквизиты. Проверьте поля и попробуйте ещё раз.');
            return false;
        } finally {
            setRequisitesPending(false);
        }
    };

    const setRequisitesField = <Key extends keyof PartnerRequisitesPayload>(
        field: Key,
        value: PartnerRequisitesPayload[Key],
    ) => setRequisitesDraft(current => ({ ...current, [field]: value }));

    const setEntityType = (value: PartnerEntityType) => {
        setRequisitesDraft(current => ({
            ...current,
            entity_type: value,
            tax_id: '',
            kpp: value === 'legal_entity' ? '' : null,
        }));
    };

    const availableAmount = useMemo(
        () => Number(dashboard?.available ?? 0),
        [dashboard?.available],
    );

    return {
        user,
        dashboard,
        landings,
        payouts,
        requisites,
        requisitesDraft,
        loading,
        error,
        notice,
        payoutAmount,
        payoutPending,
        requisitesPending,
        availableAmount,
        setPayoutAmount,
        setRequisitesField,
        setEntityType,
        requestPayout,
        saveRequisites,
        reload: load,
        logout,
    };
};

export type PartnerCabinetViewModel = ReturnType<typeof usePartnerCabinet>;
