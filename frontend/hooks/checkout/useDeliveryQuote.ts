'use client';

import { useEffect, useState, useSyncExternalStore } from 'react';
import { DeliveryQuoteController, quoteRequestKey } from '@/lib/checkout/quote';
import type { DeliveryCalculationRequest } from '@/lib/checkout/types';

export function useDeliveryQuote(request: DeliveryCalculationRequest | null, active: boolean, cartRevision: string) {
    const [controller] = useState(() => new DeliveryQuoteController());
    const [retry, setRetry] = useState(0);
    const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
    const key = quoteRequestKey(request);
    useEffect(() => {
        const destination = key ? JSON.parse(key) as DeliveryCalculationRequest : null;
        void controller.update(destination, active);
        return controller.cancel;
    }, [controller, key, active, cartRevision, retry]);
    useEffect(() => {
        if (!state.quote || !active || !key) return;
        const timer = setTimeout(() => {
            controller.expire();
            void controller.update(JSON.parse(key) as DeliveryCalculationRequest, true);
        }, Math.max(0, state.expiresAt - Date.now()));
        return () => clearTimeout(timer);
    }, [controller, state.quote, state.expiresAt, active, key]);
    // Hide a stale quote during render, before React runs effect cleanup.
    const current = active && state.key === key && state.status === 'ready';
    return {
        quote: current ? state.quote : null,
        quoteExpiresAt: state.expiresAt,
        quoteLoading: active && state.key === key && state.status === 'loading',
        quoteError: active && state.key === key && state.status === 'error'
            ? 'Не удалось рассчитать доставку. Проверьте адрес и попробуйте позже.' : '',
        retryQuote: () => setRetry(value => value + 1),
    };
}
