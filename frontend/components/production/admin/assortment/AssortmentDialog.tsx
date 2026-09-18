'use client';

import type { ReactNode } from 'react';
import { PiX } from 'react-icons/pi';
import styles from '../ProductionAdmin.module.css';

export function AssortmentDialog({
    title,
    description,
    onClose,
    children,
}: {
    title: string;
    description?: string;
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
                <div className={styles.dialogHeading}>
                    <div>
                        <h2 id="assortment-dialog-title">{title}</h2>
                        {description && (
                            <p className={styles.modalDescription}>
                                {description}
                            </p>
                        )}
                    </div>
                    <button
                        type="button"
                        className={styles.iconButton}
                        onClick={onClose}
                        aria-label="Закрыть окно"
                        title="Закрыть"
                    >
                        <PiX aria-hidden />
                    </button>
                </div>
                {children}
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

