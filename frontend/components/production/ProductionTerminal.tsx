'use client';
import { useEffect } from 'react';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import { ProductionAdminTerminal } from './admin/ProductionAdminTerminal';
import { ProductionLogin } from './ProductionLogin';
import { ProductionWorkspace } from './workspaces/ProductionWorkspace';
import styles from './ProductionTerminal.module.css';

export function ProductionTerminal({
    mode = 'auto',
}: {
    mode?: 'auto' | 'floor';
}) {
    const initialize = useProductionAuthStore((state) => state.initialize);
    useEffect(() => {
        void initialize();
    }, [initialize]);
    const ready = useProductionAuthStore((state) => state.isSessionReady);
    const authenticated = useProductionAuthStore(
        (state) => state.isAuthenticated,
    );
    const userId = useProductionAuthStore((state) => state.user?.id);
    const canAdminister = useProductionAuthStore(
        (state) => state.user?.can_administer,
    );
    if (!ready)
        return (
            <main className={`${styles.login} ${styles.sessionLoading}`}>
                <video
                    className={styles.sessionLogo}
                    src="/logo_anim.mp4"
                    autoPlay
                    loop
                    muted
                    playsInline
                    preload="auto"
                    aria-hidden="true"
                />
                <span className={styles.srOnly} role="status">
                    Загрузка терминала
                </span>
            </main>
        );
    if (!authenticated) return <ProductionLogin />;
    if (canAdminister && mode !== 'floor')
        return <ProductionAdminTerminal key={userId} />;
    return <ProductionWorkspace key={userId} />;
}
