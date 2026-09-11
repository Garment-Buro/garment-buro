'use client';
import {
    type AdminSection,
    type AdminOrder,
    type AdminEmployee,
    type AdminClient,
    type AdminPayout,
    date,
    money,
    sectionLabels,
    statusLabels,
    stationLabels,
} from '@/lib/production/adminTypes';
import styles from './ProductionAdmin.module.css';
export type RecordRow = AdminOrder | AdminPayout | AdminEmployee | AdminClient;
function Contact({
    name,
    email,
    phone,
}: {
    name: string;
    email: string | null;
    phone: string | null;
}) {
    return (
        <>
            <strong>{name || 'Имя не указано'}</strong>
            <small>{email || 'Без почты'}</small>
            <small>{phone || 'Без телефона'}</small>
        </>
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
}: {
    section: Exclude<AdminSection, 'stats'>;
    items: RecordRow[];
    onOrder: (id: number) => void;
    onPayout: (payout: AdminPayout) => void;
    onEmployee: (employee: AdminEmployee) => void;
}) {
    return (
        <table>
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
                                <td data-label="Заказ">
                                    <button onClick={() => onOrder(row.id)}>
                                        №{row.id}
                                    </button>
                                    <small>{date(row.created_at)}</small>
                                </td>
                                <td data-label="Покупатель">
                                    <Contact {...row} />
                                </td>
                                <td data-label="Этап">
                                    <Status
                                        value={row.workflow_state || row.status}
                                    />
                                </td>
                                <td data-label="Оплата">
                                    <Status value={row.payment_status} />
                                </td>
                                <td data-label="Сумма">{money(row.total)}</td>
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
                                <td data-label="Сотрудник">
                                    <Contact {...row} />
                                    <small>Сотрудник №{row.id}</small>
                                </td>
                                <td data-label="Участки">
                                    <strong>
                                        Основной: {stationLabels[row.primary_station]}
                                    </strong>
                                    <small>
                                        {row.stations
                                            .map((station) => stationLabels[station])
                                            .join(', ')}
                                    </small>
                                </td>
                                <td data-label="Доступ">
                                    <Status value={row.status} />
                                    <small>
                                        {row.code_active
                                            ? 'Личный код действует'
                                            : 'Действующего кода нет'}
                                    </small>
                                </td>
                                <td data-label="Добавлен">{date(row.created_at)}</td>
                                <td data-label="Управление">
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
                                <td data-label="Клиент">
                                    <Contact {...row} />
                                    <small>
                                        {row.user_id
                                            ? `Аккаунт №${row.user_id}`
                                            : 'Гостевые заказы'}
                                    </small>
                                </td>
                                <td data-label="Заказов">{row.orders_count}</td>
                                <td data-label="Сумма заказов">{money(row.orders_total)}</td>
                                <td data-label="Оплаченные заказы">
                                    {money(row.paid_orders_total)}
                                </td>
                                <td data-label="Последний заказ">
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
                                <td data-label="Заявка">
                                    №{row.id}
                                    <small>{date(row.created_at)}</small>
                                </td>
                                <td data-label="Партнёр">
                                    {row.partner}
                                    <small>Партнёр №{row.partner_id}</small>
                                </td>
                                <td data-label="Сумма">{money(row.amount)}</td>
                                <td data-label="Состояние">
                                    <Status value={row.status} />
                                    <small>
                                        {row.bank_state
                                            ? `Банк: ${statusLabels[row.bank_state] || row.bank_state}`
                                            : 'Не передана в банк'}
                                    </small>
                                    {row.note && <small>{row.note}</small>}
                                </td>
                                <td data-label="Решение">
                                    {!row.bank_state &&
                                    ['requested', 'approved'].includes(
                                        row.status,
                                    ) ? (
                                        <button
                                            onClick={() => {
                                                onPayout(row);
                                            }}
                                        >
                                            Рассмотреть
                                        </button>
                                    ) : (
                                        'Решение недоступно'
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </>
            )}
        </table>
    );
}
