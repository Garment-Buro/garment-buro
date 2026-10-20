'use client';

import type { ReactNode } from 'react';
import { ServiceCatalogSheet } from './ServiceCatalogSheet';
import styles from './ServiceFavoritesSheet.module.css';

export function ServiceFavoritesSheet({ children, count, countLabel = 'Товаров в избранном', hasMore = false, onClose }: {
    children: ReactNode; count: number; countLabel?: string; hasMore?: boolean; onClose: () => void;
}) {
    return <ServiceCatalogSheet title="ИЗБРАННОЕ" onClose={onClose} className={styles.sheet}
        headerAction={<span aria-label={`${countLabel}: ${count}${hasMore ? ', есть ещё' : ''}`} aria-live="polite">{String(count).padStart(2, '0')}{hasMore ? '+' : ''}</span>}>
        {children}
    </ServiceCatalogSheet>;
}
