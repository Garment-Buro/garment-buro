"use client";

import { useState } from 'react';

import { formatPartnerDate, formatPartnerMoney } from '@/lib/partners/format';
import type { usePartnerPayouts } from '@/hooks/partner/usePartnerPayouts';
import type { PartnerPayout } from '@/lib/partners/types';

import styles from './PartnerDashboard.module.css';

const STATUS_LABELS: Record<PartnerPayout['status'], string> = {
    requested: 'На проверке',
    approved: 'Одобрена',
    paid: 'Выплачена',
    rejected: 'Отклонена',
    canceled: 'Отменена',
};

const statusClassName = (status: PartnerPayout['status']) => {
    if (status === 'paid') return `${styles.status} ${styles.statusPaid}`;
    if (status === 'rejected' || status === 'canceled') {
        return `${styles.status} ${styles.statusRejected}`;
    }
    return styles.status;
};

export const PartnerPayoutHistory = ({ payouts }: { payouts: ReturnType<typeof usePartnerPayouts> }) => {
    const [expanded, setExpanded] = useState(false);
    const visiblePayouts = expanded ? payouts.items : payouts.items.slice(0, 3);

    return (
        <section className={styles.panel} aria-labelledby="payout-history-title">
            <div className={styles.panelHeader}>
                <div>
                    <p className={styles.sectionEyebrow}>Движение денег</p>
                    <h2 id="payout-history-title">История выплат</h2>
                </div>
                {(payouts.items.length > 3 || payouts.hasMore) && (
                    <button
                        type="button"
                        className={styles.textButton}
                        onClick={() => setExpanded(value => !value)}
                        aria-expanded={expanded}
                    >
                        {expanded ? 'Свернуть' : 'Все'}
                    </button>
                )}
            </div>

            {payouts.loading && <p role="status">Загружаем выплаты…</p>}
            {payouts.message && <p role="alert">{payouts.message} <button type="button" onClick={() => void payouts.retry()}>Обновить выплаты</button></p>}
            {visiblePayouts.length > 0 ? (
                <div className={styles.historyList}>
                    {visiblePayouts.map(payout => (
                        <article className={styles.historyRow} key={payout.id}>
                            <div>
                                <p className={styles.historyAmount}>{formatPartnerMoney(payout.amount)}</p>
                                <p className={styles.historyDate}>{formatPartnerDate(payout.created_at)}</p>
                            </div>
                            <span className={statusClassName(payout.status)}>
                                {STATUS_LABELS[payout.status]}
                            </span>
                        </article>
                    ))}
                </div>
            ) : !payouts.loading && !payouts.message ? (
                <p className={styles.emptyText}>Выплат пока не было. Первая заявка появится здесь.</p>
            ) : null}
            {expanded && payouts.hasMore && <button type="button" className={styles.secondaryButton} disabled={payouts.loadingMore} onClick={() => void payouts.loadMore()}>{payouts.loadingMore ? 'Загружаем…' : 'Ещё выплаты'}</button>}
        </section>
    );
};
