'use client';

import type { PendingPurchase } from '@/lib/checkout/operation';

export function PurchaseRecovery({ pending, busy, onResume, onRetry, onNew }: {
    pending: PendingPurchase | null; busy: boolean; onResume: () => void; onRetry: () => void; onNew: () => void;
}) {
    if (!pending) return null;
    return <section className="px-6 py-4 text-sm" aria-label="Сохранённое оформление">
        <p>{pending.orderId ? `Заказ #${pending.orderId}` : 'Незавершённое оформление'}</p>
        <p>{pending.payload.items.reduce((sum, item) => sum + item.quantity, 0)} шт. · {pending.payload.claimed_total_price.toLocaleString('ru-RU')} ₽</p>
        <p>{pending.payload.delivery_address}</p>
        <p>{pending.status === 'review' ? 'Заказ сохранён. Состояние платежа требует проверки менеджера; повторная оплата недоступна.' : pending.status === 'rejected' ? 'Заказ сохранён, оплата отклонена.' : pending.status === 'complete'
            ? 'Заказ сохранён. Можно перейти к нему или начать новый заказ.'
            : 'Продолжение проверит исходный заказ с указанными выше товарами и адресом.'}</p>
        <button type="button" disabled={busy} onClick={pending.status === 'rejected' ? onRetry : onResume} className="my-2 underline disabled:opacity-50">
            {busy ? 'Проверяем…' : pending.status === 'rejected' ? 'Повторить оплату заказа' : ['complete', 'review'].includes(pending.status) ? 'Перейти к заказу' : 'Продолжить исходное оформление'}
        </button>
        {['complete', 'review'].includes(pending.status) && <button type="button" disabled={busy} onClick={onNew} className="ml-4 underline disabled:opacity-50">{pending.status === 'review' ? 'Создать другой заказ' : 'Новый заказ'}</button>}
    </section>;
}
