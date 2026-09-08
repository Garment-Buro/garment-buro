export type AdminSection = 'stats' | 'orders' | 'payouts' | 'users' | 'clients';
export interface Page<T> {
    items: T[];
    next_offset: number | null;
}
export interface AdminOrder {
    id: number;
    user_id: number | null;
    name: string;
    email: string | null;
    phone: string | null;
    created_at: string;
    total: string;
    status: string;
    payment_status: string;
    workflow_state: string | null;
}
export interface AdminOrderDetail extends AdminOrder {
    delivery_city: string | null;
    delivery_address: string | null;
    delivery_method: string | null;
    pickup_point: string | null;
    delivery_price: string;
    items: {
        id: number;
        title: string;
        quantity: number;
        size: string;
        color: string;
        total: string;
        customization: Record<string, unknown> | null;
    }[];
}
export interface AdminUser {
    id: number;
    name: string;
    email: string | null;
    phone: string | null;
    status: string;
    created_at: string;
    roles: string[];
}
export interface AdminClient {
    key: string;
    user_id: number | null;
    last_order_id: number;
    name: string;
    email: string | null;
    phone: string | null;
    last_order_at: string;
    orders_count: number;
    orders_total: string;
    paid_orders_total: string;
}
export interface AdminPayout {
    id: number;
    partner_id: number;
    partner: string;
    amount: string;
    status: string;
    bank_state: string | null;
    note: string | null;
    created_at: string;
    reviewed_at: string | null;
    paid_at: string | null;
}
export interface AdminStats {
    as_of: string;
    orders_count: number;
    orders_total: string;
    paid_orders_total: string;
    users_count: number;
    clients_count: number;
    order_states: { status: string; count: number }[];
    payout_states: { status: string; count: number; amount: string }[];
}
export const sectionLabels: Record<AdminSection, string> = {
    stats: 'Статистика',
    orders: 'Все заказы',
    payouts: 'Заявки на выплаты',
    users: 'Пользователи',
    clients: 'Клиенты',
};
export const roleLabels: Record<string, string> = {
    customer: 'Покупатель',
    partner: 'Партнёр',
    manager: 'Менеджер',
    admin: 'Администратор платформы',
    production_admin: 'Администратор терминала',
    production_tech: 'Технолог',
    production_kit: 'Комплектовка',
    production_cut: 'Раскрой',
    production_dtf: 'Печать DTF',
    production_application: 'Нанесение',
    production_sewing: 'Пошив',
    production_press: 'ВТО',
    production_qc: 'ОТК',
    production_packing: 'Упаковка',
    production_shipping: 'Отправка',
};
export const statusLabels: Record<string, string> = {
    new: 'Новый',
    processing: 'В обработке',
    pending: 'Ожидает оплаты',
    paid: 'Оплачено',
    failed: 'Ошибка оплаты',
    moderation: 'Модерация',
    production: 'Производство',
    shipped: 'Передано в СДЭК',
    completed: 'Выполнен',
    cancelled: 'Отменён',
    canceled: 'Отменена',
    awaiting_payment: 'Ожидает оплаты',
    capture_pending: 'Подтверждение списания',
    cancel_pending: 'Отмена холда',
    attention: 'Требует внимания',
    requested: 'На рассмотрении',
    approved: 'Одобрена',
    rejected: 'Отклонена',
    active: 'Активен',
    blocked: 'Заблокирован',
    deleted: 'Удалён',
    awaiting_signature: 'На подписи в банке',
    submitting: 'Создание платёжки',
    unknown: 'Нужна сверка с банком',
};
export const money = (amount: string) =>
    new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        maximumFractionDigits: 2,
    }).format(Number(amount));
export const date = (value: string) => new Date(value).toLocaleString('ru-RU');
