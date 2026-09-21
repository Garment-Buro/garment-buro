'use client';
import {
    type AdminSection,
    type AdminOrder,
    type AdminEmployee,
    type AdminClient,
    type AdminPayout,
    type AdminInboxItem,
    date,
    money,
    priorityLabels,
    sectionLabels,
    statusLabels,
    stationLabels,
} from '@/lib/production/adminTypes';
import styles from './ProductionAdmin.module.css';
export type RecordRow =
    | AdminOrder
    | AdminPayout
    | AdminEmployee
    | AdminClient
    | AdminInboxItem;
function Contact({
    name,
    email,
    phone,
    onClick,
}: {
    name: string;
    email: string | null;
    phone: string | null;
    onClick?: () => void;
}) {
    const content = (
        <>
            <strong>{name || 'Имя не указано'}</strong>
            <small className={styles.contactDetails}>
                {[email, phone].filter(Boolean).join(' · ') || 'Без контактов'}
            </small>
        </>
    );
    return onClick ? (
        <button
            type="button"
            className={styles.contactButton}
            onClick={onClick}
        >
            {content}
        </button>
    ) : (
        <span className={styles.contactBlock}>{content}</span>
    );
}
function Status({ value }: { value: string }) {
    return <span className={styles.badge}>{statusLabels[value] || value}</span>;
}

export function AdminRecordsTable({
    section,
    items,
    onOrder,
    onPayout,
    onEmployee,
    onInbox,
    onClient,
    onCode,
    codeBusyId,
}: {
    section: Exclude<AdminSection, 'stats'>;
    items: RecordRow[];
    onOrder: (id: number) => void;
    onPayout: (payout: AdminPayout) => void;
    onEmployee: (employee: AdminEmployee) => void;
    onInbox: (item: AdminInboxItem) => void;
    onClient: (client: AdminOrder | AdminClient) => void;
    onCode: (employee: AdminEmployee) => void;
    codeBusyId: number | null;
}) {
    return (
        <table data-section={section}>
            <caption className={styles.srOnly}>
                {sectionLabels[section]}
            </caption>
            {section === 'orders' && (
                <>
                    <thead>
                        <tr>
                            <th>Заказ</th>
                            <th>Покупатель</th>
                            <th>Этап</th>
                            <th>Оплата</th>
                            <th>Сумма</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(items as AdminOrder[]).map((row) => (
                            <tr key={row.id}>
                                <td
                                    data-label="Заказ"
                                    data-primary="true"
                                    data-field="order"
                                >
                                    <button onClick={() => onOrder(row.id)}>
                                        №{row.id}
                                    </button>
                                    <small>{date(row.created_at)}</small>
                                </td>
                                <td
                                    data-label="Покупатель"
                                    data-wide="true"
                                    data-field="client"
                                >
                                    <Contact
                                        {...row}
                                        onClick={() => onClient(row)}
                                    />
                                </td>
                                <td data-label="Этап" data-field="status">
                                    <Status
                                        value={row.workflow_state || row.status}
                                    />
                                </td>
                                <td data-label="Оплата" data-field="payment">
                                    <Status value={row.payment_status} />
                                </td>
                                <td
                                    data-label="Сумма"
                                    data-tail="true"
                                    data-field="total"
                                >
                                    {money(row.total)}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </>
            )}
            {section === 'employees' && (
                <>
                    <thead>
                        <tr>
                            <th>Сотрудник</th>
                            <th>Участки</th>
                            <th>Доступ</th>
                            <th>Добавлен</th>
                            <th>Управление</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(items as AdminEmployee[]).map((row) => (
                            <tr key={row.id}>
                                <td data-label="Сотрудник" data-primary="true">
                                    <Contact {...row} />
                                    {row.is_production_admin && (
                                        <span className={styles.demoBadge}>
                                            Производственный администратор
                                        </span>
                                    )}
                                    <small>Сотрудник №{row.id}</small>
                                </td>
                                <td data-label="Участки">
                                    <strong>
                                        Основной:{' '}
                                        {stationLabels[row.primary_station]}
                                    </strong>
                                    <small>
                                        {row.stations
                                            .map(
                                                (station) =>
                                                    stationLabels[station],
                                            )
                                            .join(', ')}
                                    </small>
                                </td>
                                <td data-label="Доступ">
                                    <Status
                                        value={
                                            row.status === 'blocked'
                                                ? 'blocked'
                                                : row.availability || 'available'
                                        }
                                    />
                                    {row.code_active ? (
                                        <button
                                            type="button"
                                            className={styles.maskedCode}
                                            aria-label={`Показать новый код сотрудника ${row.name}`}
                                            title="Показать новый код"
                                            disabled={codeBusyId !== null}
                                            onClick={() => onCode(row)}
                                        >
                                            {codeBusyId === row.id
                                                ? '•••'
                                                : '***'}
                                        </button>
                                    ) : (
                                        <small>Код не выдан</small>
                                    )}
                                </td>
                                <td data-label="Добавлен" data-tail="true">
                                    {date(row.created_at)}
                                </td>
                                <td data-label="Управление" data-action="true">
                                    <button onClick={() => onEmployee(row)}>
                                        Изменить
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </>
            )}
            {section === 'clients' && (
                <>
                    <thead>
                        <tr>
                            <th>Клиент</th>
                            <th>Заказов</th>
                            <th>Сумма заказов</th>
                            <th>Оплаченные заказы</th>
                            <th>Последний заказ</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(items as AdminClient[]).map((row) => (
                            <tr key={row.key}>
                                <td data-label="Клиент" data-primary="true">
                                    <Contact
                                        {...row}
                                        onClick={() => onClient(row)}
                                    />
                                    <small>
                                        {row.user_id
                                            ? `Аккаунт №${row.user_id}`
                                            : 'Гостевые заказы'}
                                    </small>
                                </td>
                                <td data-label="Заказов">{row.orders_count}</td>
                                <td data-label="Сумма заказов">
                                    {money(row.orders_total)}
                                </td>
                                <td data-label="Оплаченные заказы" data-tail="true">
                                    {money(row.paid_orders_total)}
                                </td>
                                <td data-label="Последний заказ" data-action="true">
                                    <button
                                        onClick={() =>
                                            onOrder(row.last_order_id)
                                        }
                                    >
                                        №{row.last_order_id}
                                    </button>
                                    <small>{date(row.last_order_at)}</small>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </>
            )}
            {section === 'payouts' && (
                <>
                    <thead>
                        <tr>
                            <th>Заявка</th>
                            <th>Партнёр</th>
                            <th>Сумма</th>
                            <th>Состояние</th>
                            <th>Решение</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(items as AdminPayout[]).map((row) => (
                            <tr key={row.id}>
                                <td
                                    data-label="Заявка"
                                    data-primary="true"
                                    data-field="payout"
                                >
                                    <button
                                        type="button"
                                        onClick={() => onPayout(row)}
                                    >
                                        №{row.id}
                                    </button>
                                    <small>{date(row.created_at)}</small>
                                </td>
                                <td
                                    data-label="Партнёр"
                                    data-wide="true"
                                    data-field="partner"
                                >
                                    {row.partner}
                                    <small>Партнёр №{row.partner_id}</small>
                                </td>
                                <td data-label="Сумма" data-field="amount">
                                    {money(row.amount)}
                                </td>
                                <td data-label="Состояние" data-field="state">
                                    <Status value={row.status} />
                                    <small>
                                        {row.bank_state
                                            ? `Банк: ${statusLabels[row.bank_state] || row.bank_state}`
                                            : 'Не передана в банк'}
                                    </small>
                                    {row.note && <small>{row.note}</small>}
                                </td>
                                <td
                                    data-label="Решение"
                                    data-action="true"
                                    data-field="action"
                                >
                                    <button onClick={() => onPayout(row)}>
                                        {!row.bank_state &&
                                        ['requested', 'approved'].includes(
                                            row.status,
                                        )
                                            ? 'Рассмотреть'
                                            : 'Посмотреть'}
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </>
            )}
            {(section === 'support' || section === 'problems') && (
                <>
                    <thead>
                        <tr>
                            <th>Обращение</th>
                            <th>
                                {section === 'support' ? 'Пользователь' : 'Производство'}
                            </th>
                            <th>Приоритет</th>
                            <th>Статус</th>
                            <th>Создано</th>
                            <th>Управление</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(items as AdminInboxItem[]).map((row) => (
                            <tr key={row.id}>
                                <td data-label="Обращение" data-primary="true">
                                    <strong>{row.subject}</strong>
                                    <small>№{row.id}</small>
                                </td>
                                <td
                                    data-wide="true"
                                    data-label={
                                        section === 'support'
                                            ? 'Пользователь'
                                            : 'Производство'
                                    }
                                >
                                    <strong>{row.reporter_name || 'Не указан'}</strong>
                                    <small>
                                        {section === 'support'
                                            ? row.order_id
                                                ? `Заказ №${row.order_id}`
                                                : row.reporter_email || 'Без контактов'
                                            : [
                                                  row.station && stationLabels[
                                                      row.station as keyof typeof stationLabels
                                                  ],
                                                  row.project_id && `Проект №${row.project_id}`,
                                              ]
                                                  .filter(Boolean)
                                                  .join(' · ') || 'Без привязки'}
                                    </small>
                                </td>
                                <td data-label="Приоритет">
                                    <span
                                        className={`${styles.badge} ${
                                            row.priority === 'critical'
                                                ? styles.criticalBadge
                                                : row.priority === 'high'
                                                  ? styles.highBadge
                                                  : ''
                                        }`}
                                    >
                                        {priorityLabels[row.priority]}
                                    </span>
                                </td>
                                <td data-label="Статус">
                                    <Status value={row.status} />
                                    <small>
                                        {row.assigned_to_user_id
                                            ? `Ответственный №${row.assigned_to_user_id}`
                                            : 'Без ответственного'}
                                    </small>
                                </td>
                                <td data-label="Создано" data-tail="true">
                                    {date(row.created_at)}
                                </td>
                                <td data-label="Управление" data-action="true">
                                    <button onClick={() => onInbox(row)}>
                                        Открыть
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </>
            )}
        </table>
    );
}
