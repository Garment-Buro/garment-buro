export interface CustomerOrderState {
    status?: string | null;
    payment_status?: string | null;
    customer_stage?: string | null;
    customer_stage_label?: string | null;
}

const statusLabels: Record<string, string> = {
    new: 'Заказ создан', processing: 'В обработке', shipped: 'Отправлен',
    completed: 'Выполнен', delivered: 'Доставлен', cancelled: 'Отменён',
    pending: 'Ожидает подтверждения',
};
const paymentLabels: Record<string, string> = {
    pending: 'Оплата не подтверждена', paid: 'Оплата подтверждена', failed: 'Оплата не прошла',
};

/** Present server facts; a created order or return URL never proves payment. */
export function customerOrderStatus(order: CustomerOrderState): {
    label: string; paymentLabel: string; tone: 'neutral' | 'success' | 'error';
} {
    const label = order.customer_stage_label?.trim() || statusLabels[order.status ?? ''] || 'Статус заказа уточняется';
    const paymentLabel = paymentLabels[order.payment_status ?? ''] || 'Статус оплаты неизвестен';
    let tone: 'neutral' | 'success' | 'error' = 'neutral';
    if (order.status === 'cancelled' || order.customer_stage === 'cancelled') tone = 'error';
    else if (order.customer_stage === 'attention') tone = 'neutral';
    else if (order.payment_status === 'failed') tone = 'error';
    else if (order.payment_status === 'paid' && (
        ['production', 'shipped', 'completed'].includes(order.customer_stage ?? '')
        || (!order.customer_stage && ['processing', 'shipped', 'completed', 'delivered'].includes(order.status ?? ''))
    )) tone = 'success';
    return { label, paymentLabel, tone };
}
