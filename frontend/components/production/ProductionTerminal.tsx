'use client';
import { useEffect } from 'react';
import Link from 'next/link';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import { ProductionAdminTerminal } from './admin/ProductionAdminTerminal';
import { ProductionLogin } from './ProductionLogin';
import { ProductionWorkspace } from './workspaces/ProductionWorkspace';
import styles from './ProductionTerminal.module.css';

export function ProductionTerminal({
    mode = 'auto',
}: {
    mode?: 'auto' | 'admin' | 'floor';
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
            <main className={styles.login}>
                <p role="status">Проверяем рабочую сессию…</p>
            </main>
        );
    if (!authenticated) return <ProductionLogin admin={mode === 'admin'} />;
    if (canAdminister && mode !== 'floor')
        return <ProductionAdminTerminal key={userId} />;
    if (mode === 'admin')
        return (
            <main className={styles.login}>
                <h1>Нет доступа</h1>
                <p>Войдите личным кодом администратора.</p>
                <Link href="/production">Вернуться в терминал</Link>
            </main>
        );
    return <ProductionWorkspace key={userId} />;
}
