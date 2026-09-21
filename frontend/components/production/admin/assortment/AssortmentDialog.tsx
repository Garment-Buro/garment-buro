'use client';

import type { ReactNode } from 'react';
import styles from '../ProductionAdmin.module.css';

export function AssortmentDialog({
    title,
    description,
    headerActions,
    onClose,
    children,
}: {
    title: string;
    description?: ReactNode;
    headerActions?: ReactNode;
    onClose: () => void;
    children: ReactNode;
}) {
    return (
        <div className={styles.modalBackdrop} role="presentation">
            <section
                className={styles.assortmentDialog}
                role="dialog"
                aria-modal="true"
                aria-labelledby="assortment-dialog-title"
            >
                <header className={styles.dialogHeading}>
                    <div>
                        <h2 id="assortment-dialog-title">{title}</h2>
                        {description && (
                            <p className={styles.modalDescription}>
                                {description}
                            </p>
                        )}
                    </div>
                    <div className={styles.dialogHeaderActions}>
                        {headerActions}
                        <button type="button" onClick={onClose}>
                            Закрыть
                        </button>
                    </div>
                </header>
                <div className={styles.assortmentDialogBody}>{children}</div>
            </section>
        </div>
    );
}

export function AssortmentFeedback({
    loading,
    error,
    empty,
}: {
    loading: boolean;
    error: string;
    empty: boolean;
}) {
    if (error)
        return (
            <p className={styles.error} role="alert">
                {error}
            </p>
        );
    if (loading)
        return (
            <div className={styles.assortmentSkeleton} role="status">
                <span />
                <span />
                <span />
                <span className={styles.srOnly}>Загружаем данные</span>
            </div>
        );
    if (empty)
        return (
            <div className={styles.empty}>
                <h3>Пока нет записей</h3>
                <p>Добавьте первую запись, чтобы настроить этот раздел.</p>
            </div>
        );
    return null;
}

export const numberOrNull = (value: FormDataEntryValue | null) => {
    const normalized = String(value ?? '').trim();
    return normalized ? Number(normalized) : null;
};

export const textOrNull = (value: FormDataEntryValue | null) => {
    const normalized = String(value ?? '').trim();
    return normalized || null;
};
