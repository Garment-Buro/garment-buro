'use client';
import { useState } from 'react';
import { useAdminResource } from '@/hooks/production/useAdminResource';
import {
    type AdminSection,
    type Page,
    type AdminPayout,
    sectionLabels,
    statusLabels,
} from '@/lib/production/adminTypes';
import { AdminOrderDetails } from './AdminOrderDetails';
import { AdminPayoutReview } from './AdminPayoutReview';
import { AdminRecordsTable, type RecordRow } from './AdminRecordsTable';
import styles from './ProductionAdmin.module.css';

type Section = Exclude<AdminSection, 'stats'>;

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
    users: ['active', 'blocked', 'deleted'],
    clients: [],
};
export function AdminRecords({ section }: { section: Section }) {
    const [search, setSearch] = useState('');
    const [query, setQuery] = useState('');
    const [status, setStatus] = useState('');
    const [offset, setOffset] = useState(0);
    const [orderId, setOrderId] = useState<number | null>(null);
    const [payout, setPayout] = useState<AdminPayout | null>(null);
    const [notice, setNotice] = useState('');
    const params = new URLSearchParams({
        q: query,
        status,
        offset: String(offset),
        limit: '30',
    });
    const { data, loading, error, reload } = useAdminResource<Page<RecordRow>>(
        `${section}?${params}`,
    );
    return (
        <section aria-busy={loading}>
            <div className={styles.sectionHeading}>
                <h2>{sectionLabels[section]}</h2>
                <button
                    disabled={loading}
                    onClick={() => {
                        setPayout(null);
                        reload();
                    }}
                >
                    Обновить
                </button>
            </div>
            <form
                className={styles.toolbar}
                onSubmit={(event) => {
                    event.preventDefault();
                    setOffset(0);
                    setQuery(search.trim());
                    setOrderId(null);
                    setPayout(null);
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
                                : 'Номер, имя, почта или телефон'
                        }
                        onChange={(event) => setSearch(event.target.value)}
                    />
                </label>
                {filters[section].length > 0 && (
                    <label>
                        Статус
                        <select
                            value={status}
                            onChange={(event) => {
                                setStatus(event.target.value);
                                setOffset(0);
                                setPayout(null);
                                setOrderId(null);
                            }}
                        >
                            <option value="">Все статусы</option>
                            {filters[section].map((value) => (
                                <option key={value} value={value}>
                                    {statusLabels[value]}
                                </option>
                            ))}
                        </select>
                    </label>
                )}
                <button type="submit" disabled={loading}>
                    Найти
                </button>
            </form>
            {section === 'clients' && (
                <p className={styles.muted}>
                    Покупатели с заказами. Контакты взяты из последнего заказа.
                    Гостевые заказы сгруппированы по почте или телефону; это не
                    подтверждённое совпадение личности.
                </p>
            )}
            {section === 'payouts' && (
                <p className={styles.muted}>
                    Одобрение заявки не отправляет деньги. Создание платёжки и
                    подпись в Точке выполняются отдельно.
                </p>
            )}
            {notice && <p role="status">{notice}</p>}
            {error && (
                <p role="alert" className={styles.error}>
                    {error}
                </p>
            )}
            {loading && <p role="status">Загружаем записи…</p>}
            {data && !data.items.length && (
                <div className={styles.empty}>
                    <h3>Записей не найдено</h3>
                    <p>
                        Проверьте поиск и выбранный статус. Новые записи
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
                    }}
                >
                    Далее
                </button>
            </div>
            {orderId !== null && (
                <AdminOrderDetails
                    key={orderId}
                    id={orderId}
                    onClose={() => setOrderId(null)}
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
        </section>
    );
}
