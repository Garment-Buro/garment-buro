'use client';

import type { ReactNode } from 'react';
import { ServiceCatalogSheet } from './ServiceCatalogSheet';
import styles from './ServiceFavoritesSheet.module.css';

export function ServiceFavoritesSheet({ children, count, onClose }: {
    children: ReactNode; count: number; onClose: () => void;
}) {
    return <ServiceCatalogSheet title="ИЗБРАННОЕ" onClose={onClose} className={styles.sheet}
        headerAction={<span aria-label={`Товаров в избранном: ${count}`} aria-live="polite">{String(count).padStart(2, '0')}</span>}>
        {children}
    </ServiceCatalogSheet>;
}
