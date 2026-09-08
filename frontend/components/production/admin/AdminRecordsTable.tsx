'use client';
import {
    type AdminSection,
    type AdminOrder,
    type AdminUser,
    type AdminClient,
    type AdminPayout,
    date,
    money,
    sectionLabels,
    statusLabels,
    roleLabels,
} from '@/lib/production/adminTypes';
import styles from './ProductionAdmin.module.css';
export type RecordRow = AdminOrder | AdminPayout | AdminUser | AdminClient;
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
}: {
    section: Exclude<AdminSection, 'stats'>;
    items: RecordRow[];
    onOrder: (id: number) => void;
    onPayout: (payout: AdminPayout) => void;
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
                                <td>
                                    <button onClick={() => onOrder(row.id)}>
                                        №{row.id}
                                    </button>
                                    <small>{date(row.created_at)}</small>
                                </td>
                                <td>
                                    <Contact {...row} />
                                </td>
                                <td>
                                    <Status
                                        value={row.workflow_state || row.status}
                                    />
                                </td>
                                <td>
                                    <Status value={row.payment_status} />
                                </td>
                                <td>{money(row.total)}</td>
                            </tr>
                        ))}
                    </tbody>
                </>
            )}
            {section === 'users' && (
                <>
                    <thead>
                        <tr>
                            <th>Аккаунт</th>
                            <th>Контакты</th>
                            <th>Роли</th>
                            <th>Статус</th>
                            <th>Регистрация</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(items as AdminUser[]).map((row) => (
                            <tr key={row.id}>
                                <td>№{row.id}</td>
                                <td>
                                    <Contact {...row} />
                                </td>
                                <td>
                                    {row.roles
                                        .map((role) => roleLabels[role] || role)
                                        .join(', ') || 'Без ролей'}
                                </td>
                                <td>
                                    <Status value={row.status} />
                                </td>
                                <td>{date(row.created_at)}</td>
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
                                <td>
                                    <Contact {...row} />
                                    <small>
                                        {row.user_id
                                            ? `Аккаунт №${row.user_id}`
                                            : 'Гостевые заказы'}
                                    </small>
                                </td>
                                <td>{row.orders_count}</td>
                                <td>{money(row.orders_total)}</td>
                                <td>{money(row.paid_orders_total)}</td>
                                <td>
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
                                <td>
                                    №{row.id}
                                    <small>{date(row.created_at)}</small>
                                </td>
                                <td>
                                    {row.partner}
                                    <small>Партнёр №{row.partner_id}</small>
                                </td>
                                <td>{money(row.amount)}</td>
                                <td>
                                    <Status value={row.status} />
                                    <small>
                                        {row.bank_state
                                            ? `Банк: ${statusLabels[row.bank_state] || row.bank_state}`
                                            : 'Не передана в банк'}
                                    </small>
                                    {row.note && <small>{row.note}</small>}
                                </td>
                                <td>
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
