import type { Project } from './types';

export type AdminSection =
    | 'stats'
    | 'orders'
    | 'payouts'
    | 'employees'
    | 'clients'
    | 'assortment'
    | 'problems'
    | 'support';
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
    moderation: {
        version: number;
        state: string;
        hold_expires_at: string | null;
        decision: string | null;
        attention: string | null;
    } | null;
    production: Project | null;
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
    'workshop',
    'application',
    'sewing',
    'press',
    'qc',
    'packing',
    'shipping',
] as const;
export type ProductionStation = (typeof productionStations)[number];
export interface AdminEmployee {
    availability: 'available' | 'sick' | 'vacation' | 'absent';
    is_production_admin: boolean;
    id: number;
    is_demo: boolean;
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
    availability: 'available' | 'sick' | 'vacation' | 'absent';
    is_production_admin: boolean;
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
export type AdminInboxStatus = 'new' | 'in_progress' | 'resolved' | 'closed';
export type AdminInboxPriority = 'low' | 'normal' | 'high' | 'critical';
export interface AdminInboxItem {
    id: number;
    kind: 'support' | 'production_problem';
    status: AdminInboxStatus;
    priority: AdminInboxPriority;
    subject: string;
    message: string;
    reporter_user_id: number | null;
    reporter_name: string | null;
    reporter_email: string | null;
    reporter_phone: string | null;
    order_id: number | null;
    project_id: number | null;
    production_unit_id: number | null;
    station: string | null;
    assigned_to_user_id: number | null;
    admin_note: string | null;
    version: number;
    resolved_at: string | null;
    created_at: string;
    updated_at: string;
}
export interface AdminStats {
    as_of: string;
    orders_count: number;
    orders_total: string;
    paid_orders_total: string;
    employees_count: number;
    clients_count: number;
    support_open_count: number;
    problems_open_count: number;
    week_change: {
        orders_count: number;
        orders_total: string;
        paid_orders_total: string;
        employees_count: number;
        clients_count: number;
        support_open_count: number;
        problems_open_count: number;
    };
    order_states: { status: string; count: number }[];
    payout_states: { status: string; count: number; amount: string }[];
}
export const sectionLabels: Record<AdminSection, string> = {
    stats: 'Статистика',
    orders: 'Все заказы',
    payouts: 'Заявки на выплаты',
    employees: 'Сотрудники',
    clients: 'Клиенты',
    assortment: 'Товары и склад',
    problems: 'Проблемы',
    support: 'Поддержка',
};
export const systemAdminSections: AdminSection[] = [
    'stats',
    'orders',
    'payouts',
    'employees',
    'clients',
    'assortment',
    'problems',
    'support',
];
export const productionAdminSections: AdminSection[] = ['orders', 'problems'];
export const stationLabels: Record<ProductionStation, string> = {
    tech: 'Технолог',
    kit: 'Комплектовка',
    cut: 'Раскрой',
    dtf: 'Печать DTF',
    workshop: 'Цех (нанесение, пошив, ВТО)',
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
    in_progress: 'В работе',
    resolved: 'Решено',
    closed: 'Закрыто',
    awaiting_signature: 'На подписи в банке',
    submitting: 'Создание платёжки',
    unknown: 'Нужна сверка с банком',
};
export const priorityLabels: Record<AdminInboxPriority, string> = {
    low: 'Низкий',
    normal: 'Обычный',
    high: 'Высокий',
    critical: 'Критический',
};
export const money = (amount: string) =>
    new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        maximumFractionDigits: 2,
    }).format(Number(amount));
export const date = (value: string) => new Date(value).toLocaleString('ru-RU');
