'use client';
import { useAdminResource } from '@/hooks/production/useAdminResource';
import {
    type AdminStats,
    date,
    money,
    statusLabels,
} from '@/lib/production/adminTypes';
import styles from './ProductionAdmin.module.css';

export function AdminStatistics() {
    const { data, loading, error, reload } =
        useAdminResource<AdminStats>('stats');
    return (
        <section aria-busy={loading}>
            <div className={styles.sectionHeading}>
                <h2>Обзор платформы</h2>
                <button onClick={reload} disabled={loading}>
                    Обновить
                </button>
            </div>
            {loading && <p role="status">Загружаем статистику…</p>}
            {error && (
                <p role="alert" className={styles.error}>
                    {error}
                </p>
            )}
            {data && (
                <>
                    <p className={styles.muted}>
                        За всё время · обновлено {date(data.as_of)}
                    </p>
                    <div className={styles.metrics}>
                        {[
                            ['Заказы', data.orders_count],
                            ['Пользователи', data.users_count],
                            ['Клиенты', data.clients_count],
                            ['Сумма заказов', money(data.orders_total)],
                            [
                                'Сумма оплаченных заказов',
                                money(data.paid_orders_total),
                            ],
                        ].map(([label, value]) => (
                            <article className={styles.card} key={label}>
                                <p>{label}</p>
                                <strong>{value}</strong>
                            </article>
                        ))}
                    </div>
                    <p className={styles.muted}>
                        Суммы включают доставку. Оплаченные заказы не равны
                        бухгалтерской выручке: возвраты и банковские комиссии
                        здесь не вычитаются.
                    </p>
                    <div className={styles.columns}>
                        <section className={styles.card}>
                            <h3>Заказы по этапам</h3>
                            {data.order_states.length ? (
                                data.order_states.map((row) => (
                                    <p className={styles.row} key={row.status}>
                                        <span>
                                            {statusLabels[row.status] ||
                                                row.status}
                                        </span>
                                        <strong>{row.count}</strong>
                                    </p>
                                ))
                            ) : (
                                <p>Заказов пока нет</p>
                            )}
                        </section>
                        <section className={styles.card}>
                            <h3>Заявки на вывод</h3>
                            {data.payout_states.length ? (
                                data.payout_states.map((row) => (
                                    <p className={styles.row} key={row.status}>
                                        <span>
                                            {statusLabels[row.status] ||
                                                row.status}{' '}
                                            · {row.count}
                                        </span>
                                        <strong>{money(row.amount)}</strong>
                                    </p>
                                ))
                            ) : (
                                <p>Заявок пока нет</p>
                            )}
                        </section>
                    </div>
                </>
            )}
        </section>
    );
}
