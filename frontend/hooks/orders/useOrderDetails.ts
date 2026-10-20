'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { ApiError } from '@/lib/api/http';
import { getOrderDetails } from '@/lib/api/orders';
import { getBrowserPurchaseController, getPurchaseIdentity } from '@/lib/checkout/browserOperation';
import { useAuthStore } from '@/store/authStore';
import type { OrderDetails } from '@/lib/orders/types';

export const useOrderDetails = (providedOrderId?: string | string[]) => {
    const params = useParams();
    const routeOrderId = providedOrderId ?? params?.id;
    const orderId = Array.isArray(routeOrderId) ? routeOrderId[0] : routeOrderId;
    const userId = useAuthStore(state => state.isAuthenticated ? state.user?.id : null);
    const ready = useAuthStore(state => state.isSessionReady && !state.sessionRestorePending && !state.logoutPending);
    const epoch = useAuthStore(state => state.accountEpoch);
    const [attempt, setAttempt] = useState(0);
    const key = `${ready}:${userId ?? 'guest'}:${epoch ?? ''}:${orderId}:${attempt}`;
    const [state, setState] = useState<{ key: string; order: OrderDetails | null; error: string }>({ key: '', order: null, error: '' });
    useEffect(() => {
        if (!ready || !orderId) return;
        const abort = new AbortController(), identity = getPurchaseIdentity();
        const current = () => {
            const now = getPurchaseIdentity();
            return !abort.signal.aborted && identity && now?.owner === identity.owner && now.generation === identity.generation;
        };
        const loadOrder = async () => {
            try {
                if (!identity) throw new ApiError('Order access required', 401);
                const order = identity.owner === 'guest'
                    ? await getOrderDetails(orderId, abort.signal, { kind: 'guest', token: getBrowserPurchaseController()?.guestTokenForOrder(Number(orderId)) ?? '' })
                    : await useAuthStore.getState().runAuthenticated(token => {
                        if (!current()) throw new DOMException('Order account changed', 'AbortError');
                        return getOrderDetails(orderId, abort.signal, { kind: 'customer', token });
                    });
                if (current()) setState({ key, order, error: '' });
            } catch (error) {
                if (current()) setState({ key, order: null, error: error instanceof ApiError && error.status === 404 ? ''
                    : error instanceof ApiError && [401, 403].includes(error.status) ? 'Для просмотра нужен вход в аккаунт владельца или сохранённый гостевой ключ в этой вкладке.'
                        : 'Не удалось загрузить заказ. Проверьте соединение и повторите попытку.' });
            }
        };
        void loadOrder();
        return () => abort.abort();
    }, [orderId, ready, key, attempt]);
    return {
        order: state.key === key ? state.order : null,
        isLoading: ready && Boolean(orderId) && state.key !== key,
        error: !ready ? 'Проверяем доступ к заказу…' : state.key === key ? state.error : '',
        retry: () => setAttempt(value => value + 1),
    };
};
