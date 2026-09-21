'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
    PiChartBar,
    PiPackage,
    PiWallet,
    PiUsers,
    PiUserCircle,
    PiSignOut,
    PiWarningCircle,
    PiLifebuoy,
    PiStorefront,
    PiFactory,
} from 'react-icons/pi';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import {
    type AdminSection,
    productionAdminSections,
    sectionLabels,
    systemAdminSections,
} from '@/lib/production/adminTypes';
import { AdminRecords } from './AdminRecords';
import { AdminStatistics } from './AdminStatistics';
import { AdminAssortment } from './AdminAssortment';
import styles from './ProductionAdmin.module.css';

const icons = {
    stats: PiChartBar,
    orders: PiPackage,
    payouts: PiWallet,
    employees: PiUsers,
    clients: PiUserCircle,
    assortment: PiStorefront,
    problems: PiWarningCircle,
    support: PiLifebuoy,
};
export function ProductionAdminTerminal() {
    const user = useProductionAuthStore((state) => state.user);
    const sections =
        user?.admin_scope === 'production'
            ? productionAdminSections
            : systemAdminSections;
    const [section, setSection] = useState<AdminSection>(sections[0]);
    const [leaving, setLeaving] = useState(false);
    const contentRef = useRef<HTMLDivElement>(null);
    const logout = useProductionAuthStore((state) => state.logout);
    const error = useProductionAuthStore((state) => state.error);
    useEffect(() => {
        if (!sections.includes(section)) setSection(sections[0]);
    }, [section, sections]);
    const selectSection = (next: AdminSection) => {
        setSection(next);
        if (window.matchMedia('(max-width: 720px)').matches) {
            requestAnimationFrame(() =>
                contentRef.current?.scrollIntoView({ block: 'start' }),
            );
        }
    };
    return (
        <main className={styles.screen}>
            <a className={styles.skip} href="#production-admin-content">
                К содержимому
            </a>
            <header className={styles.header}>
                <div className={styles.identity}>
                    <video
                        className={styles.adminLogo}
                        src="/logo_anim.mp4"
                        autoPlay
                        loop
                        muted
                        playsInline
                        preload="auto"
                        aria-hidden="true"
                    />
                    <div className={styles.identityCopy}>
                        <p className={styles.eyebrow}>
                            GARMENT BURO ·{' '}
                            {user?.admin_scope === 'production'
                                ? 'ПРОИЗВОДСТВО'
                                : 'УПРАВЛЕНИЕ'}
                        </p>
                        <h1>
                            {user?.admin_scope === 'production'
                                ? 'Производственный администратор'
                                : 'Системный администратор'}
                        </h1>
                        <p>{user?.name}</p>
                    </div>
                </div>
                <div className={styles.actions}>
                    {Boolean(user?.stations.length) && (
                        <Link
                            className={styles.headerAction}
                            href="/production/floor"
                            aria-label="Открыть производство"
                            title="Открыть производство"
                        >
                            <PiFactory aria-hidden />
                            <span className={styles.actionLabel}>
                                Производство
                            </span>
                        </Link>
                    )}
                    <button
                        className={styles.headerAction}
                        aria-label={leaving ? 'Выходим' : 'Выйти'}
                        title={leaving ? 'Выходим' : 'Выйти'}
                        disabled={leaving}
                        onClick={async () => {
                            setLeaving(true);
                            try {
                                await logout();
                            } finally {
                                setLeaving(false);
                            }
                        }}
                    >
                        <PiSignOut aria-hidden />
                        <span className={styles.actionLabel}>
                            {leaving ? 'Выходим…' : 'Выйти'}
                        </span>
                    </button>
                </div>
            </header>
            <nav className={styles.nav} aria-label="Разделы администратора">
                {sections.map((key) => {
                    const Icon = icons[key];
                    return (
                        <button
                            key={key}
                            aria-current={section === key ? 'page' : undefined}
                            aria-controls="production-admin-content"
                            onClick={() => selectSection(key)}
                        >
                            <Icon aria-hidden />
                            {sectionLabels[key]}
                        </button>
                    );
                })}
            </nav>
            <div
                ref={contentRef}
                id="production-admin-content"
                className={styles.content}
            >
                {error && (
                    <p role="alert" className={styles.error}>
                        {error}
                    </p>
                )}
                {section === 'stats' ? (
                    <AdminStatistics onNavigate={selectSection} />
                ) : section === 'assortment' ? (
                    <AdminAssortment />
                ) : (
                    <AdminRecords key={section} section={section} />
                )}
            </div>
        </main>
    );
}
