/* eslint-disable @next/next/no-img-element -- immutable order snapshot */
import { useState } from 'react';
import type { Unit } from '@/lib/production/types';
import { safeImage } from '@/lib/production/workflow';
import styles from './ProductionFlow.module.css';

const sides = [
    ['front', 'Перед'],
    ['back', 'Спина'],
    ['right', 'Правый бок'],
    ['left', 'Левый бок'],
] as const;
export function ProductionViews({
    unit,
    compact = false,
}: {
    unit: Unit;
    compact?: boolean;
}) {
    const [view, setView] = useState<string>('front');
    const raw = unit.source.customization?.modelImages;
    const images =
        raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};
    return (
        <div className={styles.views} data-compact={compact}>
            <div
                className={styles.viewTabs}
                role="group"
                aria-label="Стороны изделия"
            >
                {sides.map(([key, title]) => (
                    <button
                        key={key}
                        aria-pressed={view === key}
                        onClick={() => setView(key)}
                    >
                        {title}
                    </button>
                ))}
            </div>
            <div className={styles.viewGrid}>
                {sides.map(([key, title]) => {
                    const src = safeImage(images[key]);
                    return (
                        <figure key={key} data-active={view === key}>
                            <figcaption>{title}</figcaption>
                            {src ? (
                                <img
                                    src={src}
                                    alt={`${unit.source.title}: ${title}`}
                                />
                            ) : (
                                <div className={styles.missingImage}>
                                    В заказе нет изображения этой стороны
                                </div>
                            )}
                            <small>
                                Основа изделия. Нанесения и размеры — в данных
                                заказчика.
                            </small>
                        </figure>
                    );
                })}
            </div>
        </div>
    );
}
