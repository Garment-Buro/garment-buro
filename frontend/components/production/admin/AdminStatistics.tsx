'use client';
import {
    PiArrowClockwise,
    PiArrowUpRight,
    PiChartDonut,
    PiCheckCircle,
    PiCurrencyRub,
    PiLifebuoy,
    PiMinus,
    PiPackage,
    PiTrendDown,
    PiTrendUp,
    PiUserCircle,
    PiUsers,
    PiWallet,
    PiWarningCircle,
} from 'react-icons/pi';
import { useAdminResource } from '@/hooks/production/useAdminResource';
import {
    type AdminSection,
    type AdminStats,
    date,
    money,
    statusLabels,
} from '@/lib/production/adminTypes';
import styles from './ProductionAdmin.module.css';

const signedCount = (value: number) =>
    `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value)}`;

const signedMoney = (value: string) => {
    const amount = Number(value);
    return `${amount > 0 ? '+' : amount < 0 ? '−' : ''}${money(String(Math.abs(amount)))}`;
};

export function AdminStatistics({
    onNavigate,
}: {
    onNavigate: (section: AdminSection) => void;
}) {
    const { data, loading, error, reload } =
        useAdminResource<AdminStats>('stats', 30_000);
    const trend = (
        value: number,
        inverse = false,
    ): 'positive' | 'negative' | 'neutral' => {
        if (value === 0) return 'neutral';
        const positive = value > 0;
        return positive !== inverse ? 'positive' : 'negative';
    };
    return (
        <section aria-busy={loading}>
            <div className={styles.sectionHeading}>
                <h2>Обзор платформы</h2>
                <button
                    className={styles.iconButton}
                    aria-label="Обновить статистику"
                    title="Обновить статистику"
                    onClick={reload}
                    disabled={loading}
                >
                    <PiArrowClockwise aria-hidden />
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
                            {
                                label: 'Заказы',
                                value: data.orders_count,
                                change: data.week_change.orders_count,
                                icon: PiPackage,
                                section: 'orders' as const,
                                width: 'wide',
                            },
                            {
                                label: 'Сотрудники',
                                value: data.employees_count,
                                change: data.week_change.employees_count,
                                icon: PiUsers,
                                section: 'employees' as const,
                                width: 'wide',
                            },
                            {
                                label: 'Клиенты',
                                value: data.clients_count,
                                change: data.week_change.clients_count,
                                icon: PiUserCircle,
                                section: 'clients' as const,
                                width: 'wide',
                            },
                            {
                                label: 'Открытые проблемы',
                                value: data.problems_open_count,
                                change: data.week_change.problems_open_count,
                                icon: PiWarningCircle,
                                section: 'problems' as const,
                                inverse: true,
                            },
                            {
                                label: 'Открытые обращения',
                                value: data.support_open_count,
                                change: data.week_change.support_open_count,
                                icon: PiLifebuoy,
                                section: 'support' as const,
                                inverse: true,
                            },
                            {
                                label: 'Сумма заказов',
                                value: money(data.orders_total),
                                change: Number(data.week_change.orders_total),
                                changeLabel: signedMoney(
                                    data.week_change.orders_total,
                                ),
                                icon: PiCurrencyRub,
                                section: 'orders' as const,
                            },
                            {
                                label: 'Оплачено',
                                value: money(data.paid_orders_total),
                                change: Number(
                                    data.week_change.paid_orders_total,
                                ),
                                changeLabel: signedMoney(
                                    data.week_change.paid_orders_total,
                                ),
                                icon: PiCheckCircle,
                                section: 'orders' as const,
                            },
                        ].map((metric) => {
                            const Icon = metric.icon;
                            const tone = trend(
                                metric.change,
                                metric.inverse ?? false,
                            );
                            const TrendIcon =
                                metric.change > 0
                                    ? PiTrendUp
                                    : metric.change < 0
                                      ? PiTrendDown
                                      : PiMinus;
                            return (
                                <button
                                    type="button"
                                    className={styles.metricCard}
                                    data-width={metric.width}
                                    onClick={() =>
                                        onNavigate(metric.section)
                                    }
                                    key={metric.label}
                                >
                                    <span className={styles.metricTopline}>
                                        <span className={styles.metricIcon}>
                                            <Icon aria-hidden />
                                        </span>
                                        <PiArrowUpRight aria-hidden />
                                    </span>
                                    <span className={styles.metricLabel}>
                                        {metric.label}
                                    </span>
                                    <strong>{metric.value}</strong>
                                    <span
                                        className={styles.metricTrend}
                                        data-tone={tone}
                                    >
                                        <TrendIcon aria-hidden />
                                        {metric.changeLabel ??
                                            signedCount(metric.change)}{' '}
                                        за 7 дней
                                    </span>
                                </button>
                            );
                        })}
                    </div>
                    <div className={styles.breakdowns}>
                        <section className={styles.breakdownCard}>
                            <div className={styles.breakdownHeading}>
                                <span className={styles.breakdownTitle}>
                                    <PiChartDonut aria-hidden />
                                    <span>
                                        <h3>Заказы по этапам</h3>
                                        <small>Текущая структура очереди</small>
                                    </span>
                                </span>
                                <button
                                    className={styles.iconButton}
                                    aria-label="Открыть все заказы"
                                    title="Открыть все заказы"
                                    onClick={() => onNavigate('orders')}
                                >
                                    <PiArrowUpRight aria-hidden />
                                </button>
                            </div>
                            {data.order_states.length ? (
                                <div className={styles.breakdownList}>
                                    {data.order_states.map((row) => (
                                        <div
                                            className={styles.breakdownRow}
                                            key={row.status}
                                        >
                                            <span className={styles.breakdownName}>
                                                {statusLabels[row.status] ||
                                                    row.status}
                                            </span>
                                            <strong>{row.count}</strong>
                                            <span className={styles.progress}>
                                                <span
                                                    style={{
                                                        width: `${Math.max(
                                                            4,
                                                            (row.count /
                                                                data.orders_count) *
                                                                100,
                                                        )}%`,
                                                    }}
                                                />
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className={styles.breakdownEmpty}>
                                    Заказов пока нет
                                </p>
                            )}
                        </section>
                        <section className={styles.breakdownCard}>
                            <div className={styles.breakdownHeading}>
                                <span className={styles.breakdownTitle}>
                                    <PiWallet aria-hidden />
                                    <span>
                                        <h3>Заявки на выплаты</h3>
                                        <small>Сумма и количество по статусам</small>
                                    </span>
                                </span>
                                <button
                                    className={styles.iconButton}
                                    aria-label="Открыть заявки на выплаты"
                                    title="Открыть заявки на выплаты"
                                    onClick={() => onNavigate('payouts')}
                                >
                                    <PiArrowUpRight aria-hidden />
                                </button>
                            </div>
                            {data.payout_states.length ? (
                                <div className={styles.breakdownList}>
                                    {data.payout_states.map((row) => (
                                        <div
                                            className={styles.payoutRow}
                                            key={row.status}
                                        >
                                            <span className={styles.breakdownName}>
                                                {statusLabels[row.status] ||
                                                    row.status}
                                            </span>
                                            <small>{row.count} шт.</small>
                                            <strong>
                                                {money(row.amount)}
                                            </strong>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className={styles.breakdownEmpty}>
                                    Заявок пока нет
                                </p>
                            )}
                        </section>
                    </div>
                </>
            )}
        </section>
    );
}
