'use client';

import { useCallback, useEffect, useState, useRef } from 'react';
import { usePartnerPayouts } from './usePartnerPayouts';
import { ApiError } from '@/lib/api/http';
import { createPartnerPayout, getPartnerDashboard } from '@/lib/api/partners';
import type { PartnerDashboard } from '@/lib/partners/types';
import { useAuthStore } from '@/store/authStore';
import { useCustomerAccount, runForCustomer, isCustomerSessionCurrent } from '@/hooks/catalog/customerSession';

export const usePartnerCabinet = () => {
    const { user, logout } = useAuthStore();
    const { key, userId } = useCustomerAccount();
    const lifetime = useRef<AbortController | null>(null);
    const reading = useRef<AbortController | null>(null);
    const writingPayout = useRef(false);
    const run = useCallback(<Result>(action: (token: string) => Promise<Result>) =>
        userId !== null && key !== null ? runForCustomer(userId, action, key)
            : Promise.reject(new DOMException('Account changed', 'AbortError')), [userId,key]);
    const [dashboard, setDashboard] = useState<PartnerDashboard | null>(null);
    const [payoutsRevision, setPayoutsRevision] = useState(0);
    const payouts = usePartnerPayouts(payoutsRevision);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [readError, setReadError] = useState('');
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [payoutAmount, setPayoutAmount] = useState('');
    const [payoutPending, setPayoutPending] = useState(false);

    const load = useCallback(async (outer?: AbortSignal) => {
        reading.current?.abort();
        const controller = new AbortController(), cancel = () => controller.abort();
        reading.current = controller;
        if (outer?.aborted) controller.abort();
        outer?.addEventListener('abort', cancel, {once:true});
        setReadError('');setRefreshing(true);
        try {
            const result = await run(token => getPartnerDashboard(token, controller.signal));
            if (controller.signal.aborted) return false;
            setDashboard(result);
            return true;
        } catch (failure) {
            if (controller.signal.aborted || failure instanceof DOMException && failure.name === 'AbortError') return false;
            setReadError(failure instanceof ApiError && failure.status === 403
                ? 'Для этого аккаунта не открыт партнёрский доступ.'
                : 'Не удалось обновить сводку кабинета. Попробуйте ещё раз.');
            return false;
        } finally {
            outer?.removeEventListener('abort', cancel);
            if (reading.current === controller) {
                reading.current = null;
                if (!controller.signal.aborted) {setLoading(false);setRefreshing(false);}
            }
        }
    }, [run]);
    useEffect(() => {
        const controller = new AbortController();
        lifetime.current = controller;
        void load(controller.signal);
        return () => {controller.abort();reading.current?.abort();};
    }, [load]);
    const requestPayout = async () => {
        const signal = lifetime.current?.signal;
        if (!signal || signal.aborted || !userId || !isCustomerSessionCurrent(userId,key)
            || writingPayout.current || refreshing || readError || !dashboard?.has_requisites
            || !payoutAmount || Number(payoutAmount) <= 0) return false;
        writingPayout.current = true;setPayoutPending(true);setError('');setNotice('');
        try {
            await run(token => createPartnerPayout(token, payoutAmount, signal));
            if (signal.aborted) return false;
            // The POST is confirmed even if the subsequent read is unavailable.
            setPayoutAmount('');setPayoutsRevision(value => value + 1);
            setNotice('Заявка на выплату отправлена. Мы покажем новый статус в истории.');
            await load(signal);
            return !signal.aborted;
        } catch (failure) {
            if (signal.aborted) return false;
            setError(failure instanceof ApiError && failure.message.includes('requisites')
                ? 'Сначала сохраните реквизиты для выплаты.'
                : failure instanceof ApiError && failure.status === 409
                  ? 'Сумма больше доступного баланса.' : 'Не удалось создать заявку на выплату.');
            return false;
        } finally {writingPayout.current = false;if (!signal.aborted) setPayoutPending(false);}
    };
    return {user,dashboard,payouts,loading,refreshing,readError,error,notice,payoutAmount,payoutPending,
        setPayoutAmount,requestPayout,refreshDashboard: () => load(lifetime.current?.signal),logout};
};
