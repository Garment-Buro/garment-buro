'use client';
import { useState } from 'react';
import { PiArrowClockwise } from 'react-icons/pi';
import { useAdminResource } from '@/hooks/production/useAdminResource';
import { requestJson } from '@/lib/api/http';
import {
    type AdminEmployee,
    type AdminEmployeeCodeResponse,
    type AdminClient,
    type AdminOrder,
    type AdminSection,
    type Page,
    type AdminPayout,
    employeeStations,
    sectionLabels,
    stationLabels,
    statusLabels,
} from '@/lib/production/adminTypes';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import { AdminOrderDetails } from './AdminOrderDetails';
import { AdminClientDetails } from './AdminClientDetails';
import { AdminFilters, type AdminFilterGroup } from './AdminFilters';
import { AdminEmployeeAccessCode } from './AdminEmployeeAccessCode';
import { AdminEmployeeEditor } from './AdminEmployeeEditor';
import { AdminInboxDetails } from './AdminInboxDetails';
import { AdminPayoutReview } from './AdminPayoutReview';
import { AdminRecordsTable, type RecordRow } from './AdminRecordsTable';
import styles from './ProductionAdmin.module.css';

type Section = Exclude<AdminSection, 'stats' | 'assortment'>;

const filters: Record<Section, string[]> = {
    orders: [
        'new',
        'awaiting_payment',
        'moderation',
        'capture_pending',
        'production',
        'processing',
        'shipped',
        'completed',
        'cancelled',
        'cancel_pending',
        'attention',
    ],
    payouts: ['requested', 'approved', 'paid', 'rejected', 'canceled'],
    employees: ['active', 'blocked'],
    clients: [],
    problems: ['new', 'in_progress', 'resolved', 'closed'],
    support: ['new', 'in_progress', 'resolved', 'closed'],
};
const sortingOptions = {
    orders: [
        ['created_at:desc', 'Сначала новые'],
        ['created_at:asc', 'Сначала старые'],
        ['total:desc', 'Сначала дорогие'],
        ['total:asc', 'Сначала дешёвые'],
        ['client:asc', 'Клиент: А–Я'],
        ['client:desc', 'Клиент: Я–А'],
        ['status:asc', 'По этапу'],
        ['payment_status:asc', 'По оплате'],
    ],
    payouts: [
        ['created_at:desc', 'Сначала новые'],
        ['created_at:asc', 'Сначала старые'],
        ['amount:desc', 'Сначала крупные'],
        ['amount:asc', 'Сначала небольшие'],
        ['partner:asc', 'Партнёр: А–Я'],
        ['partner:desc', 'Партнёр: Я–А'],
        ['status:asc', 'По статусу'],
    ],
} as const;
const availabilityOptions = [
    ['', 'Любое состояние'],
    ['available', 'Работает'],
    ['sick', 'Болеет'],
    ['vacation', 'В отпуске'],
    ['absent', 'Отсутствует'],
] as const;
const employeeRoleOptions = [
    ['', 'Любая роль'],
    ['manager', 'Менеджер'],
    ...employeeStations.map(
        (station) => [station, stationLabels[station]] as const,
    ),
] as const;
const priorityOptions = [
    ['', 'Любой приоритет'],
    ['critical', 'Критический'],
    ['high', 'Высокий'],
    ['normal', 'Обычный'],
    ['low', 'Низкий'],
] as const;

export function AdminRecords({
    section,
    initialQuery = '',
    onClient,
}: {
    section: Section;
    initialQuery?: string;
    onClient: (client: AdminOrder | AdminClient) => void;
}) {
    const [search, setSearch] = useState(initialQuery);
    const [query, setQuery] = useState(initialQuery);
    const [status, setStatus] = useState('');
    const [priority, setPriority] = useState('');
    const [availability, setAvailability] = useState('');
    const [station, setStation] = useState('');
    const [sorting, setSorting] = useState('created_at:desc');
    const [offset, setOffset] = useState(0);
    const [orderId, setOrderId] = useState<number | null>(null);
    const [payout, setPayout] = useState<AdminPayout | null>(null);
    const [employeeEditor, setEmployeeEditor] = useState<
        AdminEmployee | null | undefined
    >(undefined);
    const [accessCode, setAccessCode] =
        useState<AdminEmployeeCodeResponse | null>(null);
    const [notice, setNotice] = useState('');
    const [inboxId, setInboxId] = useState<number | null>(null);
    const [client, setClient] = useState<AdminClient | null>(null);
    const [actionError, setActionError] = useState('');
    const [codeBusyId, setCodeBusyId] = useState<number | null>(null);
    const run = useProductionAuthStore((state) => state.runAuthenticated);
    const isInbox = section === 'problems' || section === 'support';
    const params = new URLSearchParams({
        q: query,
        status,
        offset: String(offset),
        limit: '30',
    });
    if (isInbox) params.set('priority', priority);
    if (section === 'employees') {
        params.set('availability', availability);
        params.set('station', station);
    }
    if (section === 'orders' || section === 'payouts') {
        const [sort, direction] = sorting.split(':');
        params.set('sort', sort);
        params.set('direction', direction);
    }
    const { data, loading, error, reload } = useAdminResource<Page<RecordRow>>(
        `${section}?${params}`,
        30_000,
    );
    const filterGroups: AdminFilterGroup[] = [];
    if (filters[section].length > 0) {
        filterGroups.push({
            key: 'status',
            label: section === 'employees' ? 'Доступ' : 'Статус',
            options: [
                ['', section === 'employees' ? 'Любой доступ' : 'Все статусы'],
                ...filters[section].map(
                    (value) =>
                        [
                            value,
                            section === 'employees'
                                ? value === 'active'
                                    ? 'Доступ открыт'
                                    : 'Доступ закрыт'
                                : statusLabels[value],
                        ] as const,
                ),
            ],
        });
    }
    if (section === 'employees') {
        filterGroups.push(
            {
                key: 'availability',
                label: 'Состояние',
                options: availabilityOptions,
            },
            {
                key: 'station',
                label: 'Роль',
                options: employeeRoleOptions,
            },
        );
    }
    if (isInbox) {
        filterGroups.push({
            key: 'priority',
            label: 'Приоритет',
            options: priorityOptions,
        });
    }
    if (section === 'orders' || section === 'payouts') {
        filterGroups.push({
            key: 'sorting',
            label: 'Сортировка',
            options: sortingOptions[section],
        });
    }
    const filterValues = {
        status,
        priority,
        availability,
        station,
        sorting,
    };
    const filterDefaults = {
        status: '',
        priority: '',
        availability: '',
        station: '',
        sorting: 'created_at:desc',
    };
    return (
        <section aria-busy={loading}>
            <div className={styles.sectionHeading}>
                <h2>{sectionLabels[section]}</h2>
                <div className={styles.headingActions}>
                    {section === 'employees' && (
                        <button onClick={() => setEmployeeEditor(null)}>
                            Добавить сотрудника
                        </button>
                    )}
                    <button
                        className={styles.iconButton}
                        aria-label={`Обновить раздел «${sectionLabels[section]}»`}
                        title={`Обновить раздел «${sectionLabels[section]}»`}
                        disabled={loading}
                        onClick={() => {
                            setPayout(null);
                            setInboxId(null);
                            reload();
                        }}
                    >
                        <PiArrowClockwise aria-hidden />
                    </button>
                </div>
            </div>
            <form
                className={styles.toolbar}
                onSubmit={(event) => {
                    event.preventDefault();
                    setOffset(0);
                    setQuery(search.trim());
                    setOrderId(null);
                    setPayout(null);
                    setInboxId(null);
                }}
            >
                <label className={styles.search}>
                    Поиск
                    <input
                        value={search}
                        maxLength={100}
                        placeholder={
                            section === 'payouts'
                                ? 'Номер заявки или партнёр'
                                : isInbox
                                  ? 'Номер, тема, текст или автор'
                                : section === 'employees'
                                  ? 'Имя, телефон, почта или код сотрудника'
                                  : 'Номер, имя, почта или телефон'
                        }
                        onChange={(event) => setSearch(event.target.value)}
                    />
                </label>
                {filterGroups.length > 0 && (
                    <AdminFilters
                        groups={filterGroups}
                        values={filterValues}
                        defaults={filterDefaults}
                        onApply={(next) => {
                            setStatus(next.status);
                            setPriority(next.priority);
                            setAvailability(next.availability);
                            setStation(next.station);
                            setSorting(next.sorting);
                            setOffset(0);
                            setPayout(null);
                            setOrderId(null);
                            setInboxId(null);
                        }}
                    />
                )}
                <button type="submit" disabled={loading}>
                    Найти
                </button>
            </form>
            {section === 'payouts' && (
                <p className={styles.muted}>
                    Одобрение заявки не отправляет деньги. Создание платёжки и
                    подпись в Точке выполняются отдельно.
                </p>
            )}
            {section === 'support' && (
                <p className={styles.muted}>
                    Сообщения пользователей о заказах, оплате и работе сайта.
                    Ответы и сообщения клиентам сохраняются в личном кабинете.
                </p>
            )}
            {section === 'problems' && (
                <p className={styles.muted}>
                    Сбои и препятствия на производстве с привязкой к участку,
                    проекту или единице изделия.
                </p>
            )}
            {notice && <p role="status">{notice}</p>}
            {error && (
                <p role="alert" className={styles.error}>
                    {error}
                </p>
            )}
            {actionError && (
                <p role="alert" className={styles.error}>
                    {actionError}
                </p>
            )}
            {loading && <p role="status">Загружаем записи…</p>}
            {data && !data.items.length && (
                <div className={styles.empty}>
                    <h3>Записей не найдено</h3>
                    <p>
                        Проверьте поиск и выбранные фильтры. Новые записи
                        появятся здесь после сохранения в системе.
                    </p>
                </div>
            )}
            {data && data.items.length > 0 && (
                <div
                    className={styles.tableScroll}
                    tabIndex={0}
                    aria-label={sectionLabels[section]}
                >
                    <AdminRecordsTable
                        section={section}
                        items={data.items}
                        onOrder={setOrderId}
                        onPayout={(row) => {
                            setPayout(row);
                            setNotice('');
                        }}
                        onEmployee={(row) => {
                            setEmployeeEditor(row);
                            setNotice('');
                        }}
                        onInbox={(row) => {
                            setInboxId(row.id);
                            setNotice('');
                        }}
                        onClient={(row) => {
                            if (section === 'clients') {
                                setClient(row as AdminClient);
                            } else {
                                onClient(row);
                            }
                        }}
                        codeBusyId={codeBusyId}
                        onCode={async (employee) => {
                            if (codeBusyId !== null) return;
                            setCodeBusyId(employee.id);
                            setActionError('');
                            try {
                                const result = await run(() =>
                                    requestJson<AdminEmployeeCodeResponse>(
                                        `/production/admin/employees/${employee.id}/code`,
                                        { method: 'POST' },
                                    ),
                                );
                                setAccessCode(result);
                                reload();
                            } catch (failure) {
                                setActionError(
                                    failure instanceof Error
                                        ? failure.message
                                        : 'Не удалось выдать новый код',
                                );
                            } finally {
                                setCodeBusyId(null);
                            }
                        }}
                    />
                </div>
            )}
            <div className={styles.pagination}>
                <button
                    disabled={loading || offset === 0}
                    onClick={() => {
                        setOffset(Math.max(0, offset - 30));
                        setOrderId(null);
                        setPayout(null);
                        setInboxId(null);
                    }}
                >
                    Назад
                </button>
                <span>Страница {Math.floor(offset / 30) + 1}</span>
                <button
                    disabled={loading || data?.next_offset == null}
                    onClick={() => {
                        if (data?.next_offset != null)
                            setOffset(data.next_offset);
                        setOrderId(null);
                        setPayout(null);
                        setInboxId(null);
                    }}
                >
                    Далее
                </button>
            </div>
            {orderId !== null && (
                <AdminOrderDetails
                    key={orderId}
                    id={orderId}
                    onClient={onClient}
                    onClose={() => setOrderId(null)}
                />
            )}
            {client && (
                <AdminClientDetails
                    client={client}
                    onClose={() => setClient(null)}
                    onOrder={(id) => {
                        setClient(null);
                        setOrderId(id);
                    }}
                    onTicket={(id) => {
                        setClient(null);
                        setInboxId(id);
                    }}
                />
            )}
            {payout && (
                <AdminPayoutReview
                    key={payout.id}
                    payout={payout}
                    onClose={() => setPayout(null)}
                    onDone={() => {
                        setPayout(null);
                        setNotice('Решение сохранено. Деньги не отправлены.');
                        reload();
                    }}
                />
            )}
            {employeeEditor !== undefined && (
                <AdminEmployeeEditor
                    employee={employeeEditor}
                    onClose={() => setEmployeeEditor(undefined)}
                    onSaved={(result, message) => {
                        setEmployeeEditor(undefined);
                        setNotice(message);
                        if (result.code) setAccessCode(result);
                        reload();
                    }}
                />
            )}
            {accessCode && (
                <AdminEmployeeAccessCode
                    result={accessCode}
                    onClose={() => setAccessCode(null)}
                />
            )}
            {inboxId !== null && (isInbox || section === 'clients') && (
                <AdminInboxDetails
                    section={section === 'clients' ? 'support' : section}
                    id={inboxId}
                    onClose={() => setInboxId(null)}
                    onSaved={() => {
                        setNotice('Обращение обновлено.');
                        reload();
                    }}
                />
            )}
        </section>
    );
}
