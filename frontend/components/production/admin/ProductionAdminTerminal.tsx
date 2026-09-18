'use client';
import { useRef, useState } from 'react';
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
} from 'react-icons/pi';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import { type AdminSection, sectionLabels } from '@/lib/production/adminTypes';
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
    const [section, setSection] = useState<AdminSection>('stats');
    const [leaving, setLeaving] = useState(false);
    const contentRef = useRef<HTMLDivElement>(null);
    const user = useProductionAuthStore((state) => state.user);
    const logout = useProductionAuthStore((state) => state.logout);
    const error = useProductionAuthStore((state) => state.error);
    return (
        <main className={styles.screen}>
            <a className={styles.skip} href="#production-admin-content">
                К содержимому
            </a>
            <header className={styles.header}>
                <div>
                    <p className={styles.eyebrow}>GARMENT BURO · УПРАВЛЕНИЕ</p>
                    <h1>Терминал администратора</h1>
                    <p>{user?.name}</p>
                </div>
                <div className={styles.actions}>
                    {Boolean(user?.stations.length) && (
                        <Link href="/production/floor">Производство</Link>
                    )}
                    <button
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
                        {leaving ? 'Выходим…' : 'Выйти'}
                    </button>
                </div>
            </header>
            <nav className={styles.nav} aria-label="Разделы администратора">
                {(Object.keys(sectionLabels) as AdminSection[]).map((key) => {
                    const Icon = icons[key];
                    return (
                        <button
                            key={key}
                            aria-current={section === key ? 'page' : undefined}
                            aria-controls="production-admin-content"
                            onClick={() => {
                                setSection(key);
                                if (
                                    window.matchMedia('(max-width: 720px)')
                                        .matches
                                ) {
                                    requestAnimationFrame(() =>
                                        contentRef.current?.scrollIntoView({
                                            block: 'start',
                                        }),
                                    );
                                }
                            }}
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
                    <AdminStatistics />
                ) : section === 'assortment' ? (
                    <AdminAssortment />
                ) : (
                    <AdminRecords key={section} section={section} />
                )}
            </div>
        </main>
    );
}
