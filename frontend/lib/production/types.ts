export const stations = [
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
export type Station = (typeof stations)[number];
export type Stage =
    | 'cut'
    | 'application'
    | 'sewing'
    | 'press'
    | 'qc'
    | 'packing';
export const stages: Stage[] = [
    'cut',
    'application',
    'sewing',
    'press',
    'qc',
    'packing',
];
export const labels: Record<Station, string> = {
    tech: 'Входящие',
    kit: 'Комплектовка',
    cut: 'Раскрой',
    dtf: 'DTF печать',
    workshop: 'Цех',
    application: 'Нанесение',
    sewing: 'Пошив',
    press: 'ВТО',
    qc: 'ОТК',
    packing: 'Упаковка',
    shipping: 'Отправка',
};
export const stateLabels: Record<string, string> = {
    inbox: 'Подготовка',
    kitting: 'Комплектовка',
    workshop: 'В цехе',
    waiting_dtf: 'Ожидает DTF',
    packed: 'Упакован',
    dispatched: 'Отправлен',
    cut: 'Раскрой',
    kit: 'Комплектация',
    packing: 'Упаковка',
    done: 'Готово',
    in_production: 'В работе на участках',
};
export const actionLabels: Record<string, string> = {
    plan: 'Закреплена спецификация',
    confirm_documents: 'Подтверждены документы',
    release: 'Выпущен в работу',
    check_component: 'Проверена комплектующая',
    send_bag: 'Передан в цех',
    dtf_ready: 'DTF готов',
    insert_dtf: 'DTF вложен',
    complete_stage: 'Этап завершён',
    return_to_dtf: 'Возвращён на ожидание DTF',
    report_issue: 'Зафиксирована проблема',
    resolve_issue: 'Проблема устранена',
    rework: 'Назначена переделка',
    pack_bag: 'Мешок упакован',
    dispatch: 'Передан перевозчику',
    issue_unit_label: 'Выпущен QR мешка изделия',
    send_unit: 'Изделие передано в цех',
    complete_workshop: 'Цех завершил работу и ВТО',
    set_dtf_deadline: 'Назначен срок DTF',
};
export interface Component {
    key: string;
    name: string;
    quantity: string;
    unit: 'шт' | 'м' | 'комплект';
    location: string;
}
export interface Specification {
    tech_card_revision_id: number;
    garment_size_id: number | null;
    route: Stage[];
    components: Component[];
    pattern_file_ids: number[];
    print_file_ids: number[];
    instructions: string;
    quality_checks: string[];
}
export interface ProductionFile {
    id: number;
    name: string;
    content_type: string;
    size_bytes: number;
    sha256: string;
    card_id: number | null;
}
export interface Unit {
    lane?: string | null;
    public_token?: string | null;
    requires_dtf?: boolean;
    dtf_due_at?: string | null;
    id: number;
    number: number;
    crm_status: string;
    source: {
        title: string;
        size: string;
        color: string;
        sku: string | null;
        image: string;
        customization: Record<string, unknown> | null;
    };
    specification: Specification | null;
    specification_id: number | null;
    revision: number | null;
    stage_index: number;
    documents_confirmed: boolean;
    checks: Record<string, boolean>;
    dtf_ready: boolean;
    dtf_inserted: boolean;
    issue: string | null;
    blockers: string[];
    sizes: { id: number; code: string }[];
    cards: { id: number; name: string; revision: number }[];
    files: ProductionFile[];
}
export interface QueueItem {
    display_state?: string;
    is_demo?: boolean;
    stage_counts?: Partial<Record<Station | 'waiting_dtf', number>>;
    flow_version?: number;
    public_token?: string | null;
    dtf_pending?: number;
    project_id: number;
    order_id: number;
    customer: string;
    units_count: number;
    state: string;
    version: number;
    paid_at: string | null;
    blocked: boolean;
}
export interface Queue {
    items: QueueItem[];
    next_cursor: number | null;
}
export interface Project extends Omit<QueueItem, 'blocked'> {
    order_status: string;
    payment_status: string;
    project_status: string;
    units: Unit[];
    tracking_number: string | null;
    delivery: {
        recipient: string;
        phone: string;
        city: string;
        address: string | null;
        point_code: string | null;
        method: string;
    } | null;
    events: {
        id: number;
        version: number;
        action: string;
        unit_id: number | null;
        actor_id: number;
        at: string;
        note: string | null;
    }[];
}
export interface Employee {
    is_demo?: boolean;
    can_administer?: boolean;
    id: number;
    name: string;
    stations: Station[];
}
export interface Command {
    action:
        | 'issue_unit_label'
        | 'send_unit'
        | 'complete_workshop'
        | 'set_dtf_deadline'
        | 'plan'
        | 'confirm_documents'
        | 'release'
        | 'check_component'
        | 'send_bag'
        | 'dtf_ready'
        | 'insert_dtf'
        | 'complete_stage'
        | 'return_to_dtf'
        | 'report_issue'
        | 'resolve_issue'
        | 'rework'
        | 'pack_bag'
        | 'dispatch';
    unit_id?: number;
    specification?: Specification;
    component_key?: string;
    checked?: boolean;
    stage?: Stage;
    quality_confirmed?: number[];
    note?: string;
    tracking_number?: string;
    due_at?: string;
}
export type SendCommand = (command: Command) => Promise<boolean>;
