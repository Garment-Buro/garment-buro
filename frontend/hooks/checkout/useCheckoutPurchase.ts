'use client';

import { useCallback, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import { useCartStore } from '@/store/cartStore';
import { ApiError } from '@/lib/api/http';
import { getBrowserPurchaseController, getPurchaseIdentity } from '@/lib/checkout/browserOperation';
import { parsePendingPurchase } from '@/lib/checkout/operation';
import type { CheckoutOrderPayload } from '@/lib/checkout/types';

export function useCheckoutPurchase(active: boolean) {
    const router = useRouter();
    const userId = useAuthStore(state => state.isAuthenticated ? state.user?.id : null);
    const ready = useAuthStore(state => state.isSessionReady && !state.sessionRestorePending && !state.logoutPending);
    const epoch = useAuthStore(state => state.accountEpoch);
    const owner = ready ? userId ? `customer:${userId}` : 'guest' : '';
    const identityKey = `${owner}:${epoch ?? ''}`;
    const subscribe = useCallback((listener: () => void) => getBrowserPurchaseController()?.subscribe(listener) ?? (() => {}), []);
    const getSnapshot = useCallback(() => {
        try { return owner ? getBrowserPurchaseController()?.raw(owner) ?? null : null; } catch { return null; }
    }, [owner]);
    const raw = useSyncExternalStore(subscribe, getSnapshot, () => null);
    const pending = useMemo(() => {
        try { return parsePendingPurchase(raw, owner); } catch { return null; }
    }, [raw, owner]);
    const [feedback, setFeedback] = useState({ identityKey: '', message: '' });
    const [busyFor, setBusyFor] = useState<string | null>(null);
    const busy = useRef(false);

    const perform = async (action: 'purchase' | 'resume' | 'retry', payload?: CheckoutOrderPayload) => {
        if (!active || busy.current) return;
        const identity = getPurchaseIdentity(), controller = getBrowserPurchaseController();
        if (!identity || !controller) { setFeedback({ identityKey, message: 'Дождитесь проверки входа в аккаунт.' }); return; }
        const cartItems = useCartStore.getState().items;
        busy.current = true; setBusyFor(identityKey); setFeedback({ identityKey, message: '' });
        let submittedItems: CheckoutOrderPayload['items'] | undefined;
        try {
            submittedItems = payload?.items ?? controller.pending()?.payload.items;
            const result = action === 'resume' ? await controller.resume()
                : action === 'retry' ? await controller.retryPayment() : await controller.purchase(payload!);
            const current = getPurchaseIdentity();
            if (current?.owner !== identity.owner || current.generation !== identity.generation) return;
            const order = controller.pending();
            // A response for an older cart must not erase edits or newly added goods.
            if (order && JSON.stringify(useCartStore.getState().items) === JSON.stringify(order.payload.items)) useCartStore.getState().clearCart();
            if (result.payment_url) window.location.assign(result.payment_url);
            else router.push(`/order/${result.order_id}`);
        } catch (error) {
            const current = getPurchaseIdentity();
            if (current?.owner !== identity.owner || current.generation !== identity.generation) return;
            if (error instanceof ApiError && error.checkoutPrices && !controller.pending()) {
                const matches = submittedItems && JSON.stringify(cartItems) === JSON.stringify(submittedItems);
                const updated = matches && useCartStore.getState().applyCheckoutPrices(cartItems, error.checkoutPrices);
                setFeedback({ identityKey, message: updated
                    ? 'Цена товаров изменилась. Проверьте новую сумму и подтвердите оформление ещё раз.'
                    : 'Цена товаров изменилась. Корзина была изменена; проверьте её и повторите оформление.' });
                return;
            }
            const message = error instanceof ApiError
                ? error.code === 'payment_requires_review' ? 'Заказ сохранён. Платёж требует проверки менеджера; откройте заказ.'
                    : error.code === 'payment_rejected' ? 'Оплата отклонена. Заказ сохранён; можно повторить оплату.'
                    : error.code === 'checkout_stock_unavailable' ? 'Недостаточно товара. Измените количество или состав корзины и попробуйте снова.'
                    : error.code === 'checkout_catalog_unavailable' ? 'Товар или вариант больше недоступен. Измените состав корзины.'
                    : error.code === 'checkout_delivery_unavailable' ? 'Данные доставки изменились. Выберите доступный адрес или товар и пересчитайте доставку.'
                    : error.code === 'checkout_design_unavailable' ? 'Изображение дизайна больше недоступно. Откройте товар в конструкторе, загрузите изображение снова и повторите оформление.'
                    : error.status === 422 ? 'Проверьте данные и стоимость заказа. При необходимости пересчитайте доставку.'
                        : 'Не удалось завершить оформление. Продолжите проверку исходного заказа; корзина сохранена.'
                : error instanceof Error && error.name !== 'AbortError' && !(error instanceof TypeError) ? error.message
                    : 'Ответ не получен. Продолжите проверку исходного заказа; корзина сохранена.';
            setFeedback({ identityKey, message });
        } finally { busy.current = false; setBusyFor(null); }
    };

    return {
        pending, ready, isSubmitting: busyFor === identityKey,
        checkoutError: feedback.identityKey === identityKey ? feedback.message : '',
        purchase: (payload: CheckoutOrderPayload) => perform('purchase', payload),
        resumePurchase: () => perform('resume'), retryPayment: () => perform('retry'),
        newPurchase: () => { getBrowserPurchaseController()?.finish(); },
    };
}
