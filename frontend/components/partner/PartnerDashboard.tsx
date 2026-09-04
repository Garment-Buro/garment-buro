"use client";

import { useRef, useState } from 'react';
import { PiCheckCircle, PiWarningCircle } from 'react-icons/pi';

import { PartnerCabinetHeader } from '@/components/partner/PartnerCabinetHeader';
import { PartnerFinanceCard } from '@/components/partner/PartnerFinanceCard';
import { PartnerLandingsCard } from '@/components/partner/PartnerLandingsCard';
import { PartnerPayoutHistory } from '@/components/partner/PartnerPayoutHistory';
import { PartnerRequisitesCard } from '@/components/partner/PartnerRequisitesCard';
import { PartnerResources } from '@/components/partner/PartnerResources';
import { usePartnerCabinet } from '@/hooks/partner/usePartnerCabinet';
import { formatPartnerPercent } from '@/lib/partners/format';

import styles from './PartnerDashboard.module.css';

export const PartnerDashboard = () => {
    const cabinet = usePartnerCabinet();
    const [payoutOpen, setPayoutOpen] = useState(false);
    const [requisitesOpen, setRequisitesOpen] = useState(false);
    const requisitesRef = useRef<HTMLDivElement>(null);

    const openRequisites = () => {
        setRequisitesOpen(true);
        window.requestAnimationFrame(() => {
            requisitesRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    };

    if (cabinet.loading) return <PartnerDashboardSkeleton />;

    if (!cabinet.dashboard) {
        return (
            <div className={styles.statePage}>
                <section className={styles.stateCard}>
                    <h1>Доступ пока не открыт</h1>
                    <p>{cabinet.error}</p>
                    <button
                        type="button"
                        className={styles.primaryButton}
                        onClick={() => void cabinet.logout()}
                    >
                        Войти другим аккаунтом
                    </button>
                </section>
            </div>
        );
    }

    return (
        <div className={styles.page}>
            <a className={styles.skipLink} href="#partner-cabinet-content">
                К содержимому
            </a>
            <PartnerCabinetHeader partner={cabinet.dashboard.partner} />

            <section className={styles.sheet} id="partner-cabinet-content">
                <div className={styles.sheetHeading}>
                    <div>
                        <p className={styles.sectionEyebrow}>Финансы и продажи</p>
                        <h2 className={styles.sectionTitle}>Управление выплатами</h2>
                    </div>
                    <span className={styles.commissionBadge}>
                        Ставка {formatPartnerPercent(cabinet.dashboard.partner.commission_bps)}
                    </span>
                </div>

                {cabinet.notice && (
                    <p className={styles.notice} role="status">
                        <PiCheckCircle size={18} aria-hidden="true" />
                        {cabinet.notice}
                    </p>
                )}
                {cabinet.error && (
                    <p className={styles.error} role="alert">
                        <PiWarningCircle size={18} aria-hidden="true" />
                        {cabinet.error}
                    </p>
                )}

                <PartnerFinanceCard
                    dashboard={cabinet.dashboard}
                    hasRequisites={Boolean(cabinet.requisites)}
                    payoutAmount={cabinet.payoutAmount}
                    payoutPending={cabinet.payoutPending}
                    payoutOpen={payoutOpen}
                    onPayoutAmountChange={cabinet.setPayoutAmount}
                    onPayoutOpen={() => setPayoutOpen(true)}
                    onPayoutClose={() => setPayoutOpen(false)}
                    onPayoutSubmit={() => {
                        void cabinet.requestPayout().then(success => {
                            if (success) setPayoutOpen(false);
                        });
                    }}
                    onRequisitesRequired={openRequisites}
                />

                <div className={styles.contentGrid}>
                    <PartnerPayoutHistory payouts={cabinet.payouts} />
                    <PartnerLandingsCard landings={cabinet.landings} />
                </div>

                <div className={styles.requisitesSection} ref={requisitesRef}>
                    <PartnerRequisitesCard
                        cabinet={cabinet}
                        open={requisitesOpen}
                        onToggle={() => setRequisitesOpen(value => !value)}
                    />
                </div>

                <PartnerResources onLogout={() => void cabinet.logout()} />
            </section>
        </div>
    );
};

const PartnerDashboardSkeleton = () => (
    <div className={styles.page} aria-label="Загружаем кабинет" aria-busy="true">
        <div className={styles.hero}>
            <div className={styles.heroInner}>
                <div className={`${styles.skeleton} ${styles.skeletonLine}`} style={{ width: 160 }} />
                <div
                    className={`${styles.skeleton} ${styles.skeletonLine}`}
                    style={{ width: 'min(72%, 440px)', height: 40, marginTop: 48 }}
                />
            </div>
        </div>
        <section className={styles.sheet}>
            <div className={`${styles.skeleton} ${styles.skeletonCard}`} />
            <div className={styles.contentGrid}>
                <div className={`${styles.skeleton} ${styles.skeletonCard}`} />
                <div className={`${styles.skeleton} ${styles.skeletonCard}`} />
            </div>
        </section>
    </div>
);
