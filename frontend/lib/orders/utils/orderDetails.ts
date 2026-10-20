import type { OrderDetailRow, OrderDetails, OrderItem } from '@/lib/orders/types';
import { customerOrderStatus } from '../customerStatus.ts';

const DELIVERY_LABELS: Record<string, string> = {
    cdek_pickup: 'СДЭК ПВЗ',
    cdek_door: 'СДЭК Курьер',
};

export const parseOrderItems = (cartItems?: string | OrderItem[] | null): OrderItem[] => {
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
    { label: 'Статус', value: customerOrderStatus(order).label },
    { label: 'Сумма заказа', value: `${Number(order.total_price).toLocaleString('ru-RU')} ₽` },
    { label: 'Дата создания', value: new Date(order.created_at).toLocaleDateString('ru-RU') },
    { label: 'Доставка', value: order.delivery_method ? DELIVERY_LABELS[order.delivery_method] ?? order.delivery_method : 'Уточняется' },
    { label: 'Оплата', value: customerOrderStatus(order).paymentLabel },
    ...(order.cdek_number ? [{ label: 'Номер СДЭК', value: order.cdek_number }] : []),
    ...(order.cdek_status ? [{ label: 'Статус доставки', value: order.cdek_status }] : []),
];
