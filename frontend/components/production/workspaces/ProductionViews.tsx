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

type Decoration = {
    uid: string;
    view: string;
    image: string;
    name: string;
    x: number;
    y: number;
    widthCm: number;
    heightCm: number;
    rotation: number;
    text?: {
        content: string;
        color: string;
        fontSize: number;
    };
};

const numberValue = (value: unknown, fallback = 0) =>
    typeof value === 'number' && Number.isFinite(value) ? value : fallback;

function decorationsFrom(value: unknown): Decoration[] {
    if (!Array.isArray(value)) return [];
    return value.flatMap((raw, index) => {
        if (!raw || typeof raw !== 'object') return [];
        const item = raw as Record<string, unknown>;
        const image = safeImage(item.image ?? item.src ?? item.url) ?? '';
        const textRaw =
            item.text && typeof item.text === 'object'
                ? (item.text as Record<string, unknown>)
                : null;
        const content =
            textRaw && typeof textRaw.content === 'string'
                ? textRaw.content.slice(0, 300)
                : '';
        if (!image && !content) return [];
        return [
            {
                uid:
                    typeof item.uid === 'string'
                        ? item.uid
                        : `decoration-${index}`,
                view: typeof item.view === 'string' ? item.view : 'front',
                image,
                name:
                    typeof item.name === 'string'
                        ? item.name
                        : 'Нанесение',
                x: numberValue(item.x, 400),
                y: numberValue(item.y, 400),
                widthCm: numberValue(item.widthCm, 8),
                heightCm: numberValue(item.heightCm, 8),
                rotation: numberValue(item.rotation),
                ...(content
                    ? {
                          text: {
                              content,
                              color:
                                  typeof textRaw?.color === 'string'
                                      ? textRaw.color
                                      : '#101318',
                              fontSize: numberValue(textRaw?.fontSize, 24),
                          },
                      }
                    : {}),
            },
        ];
    });
}
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
    const customization = unit.source.customization ?? {};
    const garmentRaw = customization.garment;
    const garment =
        garmentRaw && typeof garmentRaw === 'object'
            ? (garmentRaw as Record<string, unknown>)
            : {};
    const garmentWidth = Math.min(80, Math.max(1, numberValue(garment.widthCm, 48)));
    const garmentHeight = Math.min(80, Math.max(1, numberValue(garment.heightCm, 70)));
    const decorations = decorationsFrom(customization.decorations);
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
                                <div
                                    className={styles.constructorCanvas}
                                    aria-label={`${unit.source.title}: ${title}, макет из конструктора`}
                                >
                                    <img
                                        className={styles.constructorGarment}
                                        src={src}
                                        alt=""
                                        style={{
                                            width: `${(garmentWidth / 80) * 100}%`,
                                            height: `${(garmentHeight / 80) * 100}%`,
                                        }}
                                    />
                                    {decorations
                                        .filter((item) => item.view === key)
                                        .map((item) => (
                                            <span
                                                className={styles.constructorDecoration}
                                                key={item.uid}
                                                title={item.name}
                                                style={{
                                                    left: `${(item.x / 800) * 100}%`,
                                                    top: `${(item.y / 800) * 100}%`,
                                                    width: `${(item.widthCm / 80) * 100}%`,
                                                    height: `${(item.heightCm / 80) * 100}%`,
                                                    transform: `translate(-50%, -50%) rotate(${item.rotation}deg)`,
                                                }}
                                            >
                                                {item.image ? (
                                                    <img
                                                        src={item.image}
                                                        alt={item.name}
                                                    />
                                                ) : (
                                                    <span
                                                        style={{
                                                            color: item.text?.color,
                                                            fontSize: `${Math.max(9, item.text?.fontSize ?? 24) / 2}px`,
                                                        }}
                                                    >
                                                        {item.text?.content}
                                                    </span>
                                                )}
                                            </span>
                                        ))}
                                </div>
                            ) : (
                                <div className={styles.missingImage}>
                                    В заказе нет изображения этой стороны
                                </div>
                            )}
                            <small>
                                Макет из конструктора: основа и нанесения в
                                сохранённых координатах.
                            </small>
                        </figure>
                    );
                })}
            </div>
        </div>
    );
}
