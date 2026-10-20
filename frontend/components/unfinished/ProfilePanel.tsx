"use client";

import Image from 'next/image';
import { lazy, Suspense, useState } from 'react';
import { CustomerSupport } from '@/components/support/CustomerSupport';
import type { UnfinishedSurfaceViewModel } from '@/hooks/unfinished/useUnfinishedSurface';
import { profileTabs } from '@/lib/unfinished/config/ui';
import { useAuthStore } from '@/store/authStore';
import { useCustomerAccount } from '@/hooks/catalog/customerSession';
import { ProfileSignIn } from './ProfileSignIn';
import { ProfileSettings } from './ProfileSettings';
import { ProfileOrders } from './ProfileOrders';
import styles from './UnfinishedSurface.module.css';

type ProfilePanelProps = { surface: UnfinishedSurfaceViewModel };
const LegacyProjectMigration = lazy(() => import('./LegacyProjectMigration'));

function ProfileContent({ surface }: ProfilePanelProps) {
    const account = useCustomerAccount();
    const [migrationAccount, setMigrationAccount] = useState<string | null>(null);
    const user = useAuthStore(state => state.user);
    const ready = useAuthStore(state => state.isSessionReady);
    const authenticated = useAuthStore(state => state.isAuthenticated);
    if (surface.activeProfileTab === 'support') return <CustomerSupport />;
    if (!ready) return <p role="status" className={styles.profileEmptyState}>Восстанавливаем сессию…</p>;
    if (!authenticated || !user) return <ProfileSignIn />;
    if (surface.activeProfileTab === 'discounts') return <p className={styles.profileEmptyState}>Скидки пока недоступны.</p>;
    if (surface.activeProfileTab === 'orders') return <ProfileOrders surface={surface} />;
    if (migrationAccount !== null && migrationAccount === account.key) return (
        <Suspense fallback={<p role="status" className={styles.profileEmptyState}>Открываем локальные проекты…</p>}>
            <LegacyProjectMigration key={account.key} accountEmail={user.email} onClose={() => setMigrationAccount(null)} />
        </Suspense>
    );
    return <ProfileSettings key={account.key} user={user} onMigrateProjects={() => setMigrationAccount(account.key)} />;
}

export function ProfilePanel({ surface }: ProfilePanelProps) {
    return (
        <div className={styles.profileContentShell}>
            <nav className={styles.profileTopTabs} aria-label="Разделы профиля">
                {profileTabs.map(item => (
                    <button
                        className={`${styles.surfaceButton} ${styles.profileTopTab} ${surface.activeProfileTab === item.id ? styles.profileTopTabActive : ''}`}
                        key={item.id} type="button" aria-pressed={surface.activeProfileTab === item.id}
                        aria-label={item.label || 'Скидки'} onClick={() => surface.handleSelectProfileTab(item.id)}>
                        {item.icon ? <Image src={item.icon} alt="" width={28} height={20} className={styles.profileDiscountIcon} /> : item.label}
                    </button>
                ))}
            </nav>
            <div className={styles.profileCard}><ProfileContent surface={surface} /></div>
        </div>
    );
}
