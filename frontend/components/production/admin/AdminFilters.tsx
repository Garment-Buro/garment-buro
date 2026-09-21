'use client';
import { useEffect, useState } from 'react';
import { PiFunnel, PiX } from 'react-icons/pi';
import styles from './ProductionAdmin.module.css';

export type AdminFilterGroup = {
    key: string;
    label: string;
    options: readonly (readonly [string, string])[];
};

export function AdminFilters({
    groups,
    values,
    defaults,
    onApply,
}: {
    groups: AdminFilterGroup[];
    values: Record<string, string>;
    defaults: Record<string, string>;
    onApply: (values: Record<string, string>) => void;
}) {
    const [open, setOpen] = useState(false);
    const [draft, setDraft] = useState(values);
    const activeCount = groups.filter(
        (group) => values[group.key] !== (defaults[group.key] ?? ''),
    ).length;

    useEffect(() => {
        if (!open) return;
        const closeOnEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') setOpen(false);
        };
        window.addEventListener('keydown', closeOnEscape);
        return () => window.removeEventListener('keydown', closeOnEscape);
    }, [open]);

    return (
        <>
            <button
                type="button"
                className={styles.filterButton}
                aria-expanded={open}
                onClick={() => {
                    setDraft(values);
                    setOpen(true);
                }}
            >
                <PiFunnel aria-hidden />
                Фильтры
                {activeCount > 0 && (
                    <span aria-label={`Выбрано фильтров: ${activeCount}`}>
                        {activeCount}
                    </span>
                )}
            </button>
            {open && (
                <div
                    className={styles.modalBackdrop}
                    role="presentation"
                    onMouseDown={(event) => {
                        if (event.target === event.currentTarget) setOpen(false);
                    }}
                >
                    <section
                        className={styles.filtersDialog}
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="admin-filters-title"
                    >
                        <div className={styles.dialogHeading}>
                            <div>
                                <span className={styles.eyebrow}>СПИСОК</span>
                                <h2 id="admin-filters-title">Фильтры</h2>
                            </div>
                            <button
                                type="button"
                                className={styles.iconButton}
                                aria-label="Закрыть фильтры"
                                title="Закрыть"
                                onClick={() => setOpen(false)}
                            >
                                <PiX aria-hidden />
                            </button>
                        </div>
                        <div className={styles.filterGroups}>
                            {groups.map((group) => (
                                <fieldset key={group.key}>
                                    <legend>{group.label}</legend>
                                    <div className={styles.filterOptions}>
                                        {group.options.map(([value, label]) => (
                                            <label
                                                key={value}
                                                data-selected={
                                                    draft[group.key] === value
                                                }
                                            >
                                                <input
                                                    type="radio"
                                                    name={`filter-${group.key}`}
                                                    value={value}
                                                    checked={
                                                        draft[group.key] === value
                                                    }
                                                    onChange={() =>
                                                        setDraft((current) => ({
                                                            ...current,
                                                            [group.key]: value,
                                                        }))
                                                    }
                                                />
                                                <span>{label}</span>
                                            </label>
                                        ))}
                                    </div>
                                </fieldset>
                            ))}
                        </div>
                        <div className={styles.filterActions}>
                            <button
                                type="button"
                                onClick={() => setDraft(defaults)}
                            >
                                Сбросить
                            </button>
                            <button
                                type="button"
                                className={styles.primaryButton}
                                onClick={() => {
                                    onApply(draft);
                                    setOpen(false);
                                }}
                            >
                                Показать
                            </button>
                        </div>
                    </section>
                </div>
            )}
        </>
    );
}
