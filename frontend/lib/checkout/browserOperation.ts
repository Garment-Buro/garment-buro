'use client';

import { useAuthStore } from '@/store/authStore';
import { createCheckoutOrder, retryCheckoutPayment } from '../api/checkout';
import { CheckoutOperationController, type PurchaseIdentity } from './operation';

let guestGeneration = 0;
useAuthStore.subscribe((state, previous) => {
    if (state.user?.id !== previous.user?.id || state.accountEpoch !== previous.accountEpoch
        || state.isAuthenticated !== previous.isAuthenticated) guestGeneration++;
});

export function getPurchaseIdentity(): PurchaseIdentity | null {
    const state = useAuthStore.getState();
    if (!state.isSessionReady || state.sessionRestorePending || state.logoutPending) return null;
    if (state.isAuthenticated && state.user?.id && state.token) return {
        owner: `customer:${state.user.id}`, generation: state.accountEpoch ?? `customer:${state.user.id}`,
        actor: { kind: 'customer', token: state.token },
    };
    return { owner: 'guest', generation: `guest:${guestGeneration}`, actor: { kind: 'guest', token: '' } };
}

const sameIdentity = (identity: PurchaseIdentity | null) => {
    const current = getPurchaseIdentity();
    return Boolean(identity && current?.owner === identity.owner && current?.generation === identity.generation);
};

let browserController: CheckoutOperationController | null = null;
export function getBrowserPurchaseController(): CheckoutOperationController | null {
    if (typeof window === 'undefined') return null;
    if (!browserController) browserController = new CheckoutOperationController({
        storage: {
            getItem: key => window.sessionStorage.getItem(key),
            setItem: (key, value) => window.sessionStorage.setItem(key, value),
            removeItem: key => window.sessionStorage.removeItem(key),
        },
        getIdentity: getPurchaseIdentity,
        createOrder: (payload, context) => {
            const identity = getPurchaseIdentity();
            if (context.actor.kind === 'guest') {
                if (identity?.owner !== 'guest') return Promise.reject(new DOMException('Purchase account changed', 'AbortError'));
                return createCheckoutOrder(payload, context);
            }
            return useAuthStore.getState().runAuthenticated(token => {
                if (!sameIdentity(identity)) throw new DOMException('Purchase account changed', 'AbortError');
                return createCheckoutOrder(payload, { ...context, actor: { kind: 'customer', token } });
            });
        },
        retryPayment: (orderId, context) => {
            const identity = getPurchaseIdentity();
            if (context.actor.kind === 'guest') {
                if (identity?.owner !== 'guest') return Promise.reject(new DOMException('Purchase account changed', 'AbortError'));
                return retryCheckoutPayment(orderId, context);
            }
            return useAuthStore.getState().runAuthenticated(token => {
                if (!sameIdentity(identity)) throw new DOMException('Purchase account changed', 'AbortError');
                return retryCheckoutPayment(orderId, { ...context, actor: { kind: 'customer', token } });
            });
        },
    });
    return browserController;
}
