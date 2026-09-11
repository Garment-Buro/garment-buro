export type AdminSection =
    | 'stats'
    | 'orders'
    | 'payouts'
    | 'employees'
    | 'clients';
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
export const productionStations = [
    'tech',
    'kit',
    'cut',
    'dtf',
    'application',
    'sewing',
    'press',
    'qc',
    'packing',
    'shipping',
] as const;
export type ProductionStation = (typeof productionStations)[number];
export interface AdminEmployee {
    id: number;
    first_name: string;
    last_name: string;
    name: string;
    email: string | null;
    phone: string | null;
    status: 'active' | 'blocked';
    created_at: string;
    stations: ProductionStation[];
    primary_station: ProductionStation;
    code_active: boolean;
    code_updated_at: string | null;
}
export interface AdminEmployeeWrite {
    first_name: string;
    last_name: string;
    email: string | null;
    phone: string | null;
    status: 'active' | 'blocked';
    stations: ProductionStation[];
    primary_station: ProductionStation;
}
export interface AdminEmployeeCodeResponse {
    employee: AdminEmployee;
    code: string | null;
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
    employees_count: number;
    clients_count: number;
    order_states: { status: string; count: number }[];
    payout_states: { status: string; count: number; amount: string }[];
}
export const sectionLabels: Record<AdminSection, string> = {
    stats: 'Статистика',
    orders: 'Все заказы',
    payouts: 'Заявки на выплаты',
    employees: 'Сотрудники',
    clients: 'Клиенты',
};
export const stationLabels: Record<ProductionStation, string> = {
    tech: 'Технолог',
    kit: 'Комплектовка',
    cut: 'Раскрой',
    dtf: 'Печать DTF',
    application: 'Нанесение',
    sewing: 'Пошив',
    press: 'ВТО',
    qc: 'ОТК',
    packing: 'Упаковка',
    shipping: 'Отправка',
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
