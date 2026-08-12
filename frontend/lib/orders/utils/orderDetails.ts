import type { OrderDetailRow, OrderDetails, OrderItem } from '@/lib/orders/types';

const ORDER_DETAIL_STATUS_LABELS: Record<string, string> = {
    processing: 'В обработке',
    shipped: 'Отправлен',
    delivered: 'Доставлен',
    cancelled: 'Отменён',
    pending: 'Ожидает подтверждения',
};

const DELIVERY_LABELS: Record<string, string> = {
    cdek_pickup: 'СДЭК ПВЗ',
    cdek_door: 'СДЭК Курьер',
};

export const parseOrderItems = (cartItems?: string | OrderItem[]): OrderItem[] => {
    if (Array.isArray(cartItems)) return cartItems;
    if (!cartItems) return [];

    try {
        const parsed: unknown = JSON.parse(cartItems);
        return Array.isArray(parsed) ? parsed as OrderItem[] : [];
    } catch {
        return [];
    }
};

export const getOrderFitSummary = (item: OrderItem) => {
    const fit = item.customization?.fit;
    if (!fit) return null;

    const sleeveLabel = fit.sleeveMode === 'height' ? 'под рост' : 'стандартные';
    return `Посадка: длина ${fit.lengthCm}, ширина ${fit.widthCm}, рукава ${sleeveLabel}`;
};

export const buildOrderDetailRows = (order: OrderDetails): OrderDetailRow[] => [
    { label: 'Статус', value: ORDER_DETAIL_STATUS_LABELS[order.status] ?? order.status },
    { label: 'Сумма заказа', value: `${order.total_price?.toLocaleString('ru-RU')} ₽` },
    { label: 'Дата создания', value: new Date(order.created_at).toLocaleDateString('ru-RU') },
    { label: 'Доставка', value: DELIVERY_LABELS[order.delivery_method] ?? order.delivery_method },
];
