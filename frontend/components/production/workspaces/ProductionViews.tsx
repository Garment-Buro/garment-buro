/* eslint-disable @next/next/no-img-element -- immutable order snapshot */
import { useState } from 'react';
import { PiArrowSquareOut, PiStack } from 'react-icons/pi';
import { productionApi } from '@/lib/api/production';
import type { Station, Unit } from '@/lib/production/types';
import { safeImage } from '@/lib/production/workflow';
import { useProductionAuthStore } from '@/store/productionAuthStore';
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
                name: typeof item.name === 'string' ? item.name : 'Нанесение',
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

function ConstructorPreview({
    unit,
    title,
    view,
    src,
    garmentWidth,
    garmentHeight,
    decorations,
}: {
    unit: Unit;
    title: string;
    view: string;
    src: string | null;
    garmentWidth: number;
    garmentHeight: number;
    decorations: Decoration[];
}) {
    if (!src)
        return (
            <div className={styles.missingImage}>
                В заказе нет изображения этой стороны
            </div>
        );
    return (
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
                .filter((item) => item.view === view)
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
                            <img src={item.image} alt={item.name} />
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
    );
}

export function ProductionViews({
    unit,
    compact = false,
    station,
}: {
    unit: Unit;
    compact?: boolean;
    station?: Station;
}) {
    const [view, setView] = useState<string>('front');
    const [openingFile, setOpeningFile] = useState<number | null>(null);
    const [fileError, setFileError] = useState('');
    const run = useProductionAuthStore((state) => state.runAuthenticated);
    const raw = unit.source.customization?.modelImages;
    const images =
        raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};
    const customization = unit.source.customization ?? {};
    const garmentRaw = customization.garment;
    const garment =
        garmentRaw && typeof garmentRaw === 'object'
            ? (garmentRaw as Record<string, unknown>)
            : {};
    const garmentWidth = Math.min(
        80,
        Math.max(1, numberValue(garment.widthCm, 48)),
    );
    const garmentHeight = Math.min(
        80,
        Math.max(1, numberValue(garment.heightCm, 70)),
    );
    const decorations = decorationsFrom(customization.decorations);
    const patternIds = unit.specification?.pattern_file_ids ?? [];
    const patternFiles = unit.files.filter((file) =>
        patternIds.includes(file.id),
    );
    const openPattern = async (id: number) => {
        setOpeningFile(id);
        setFileError('');
        try {
            const file = await run((token) =>
                productionApi.download(token, id, station, true),
            );
            const link = document.createElement('a');
            link.href = file.url;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.click();
        } catch (error) {
            setFileError(
                error instanceof Error ? error.message : 'Файл недоступен',
            );
        } finally {
            setOpeningFile(null);
        }
    };
    return (
        <div
            className={styles.views}
            data-compact={compact}
            data-tech={station === 'tech'}
        >
            {station !== 'tech' && (
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
            )}
            <div className={styles.viewGrid}>
                {sides.map(([key, title]) => {
                    const src = safeImage(images[key]);
                    return (
                        <figure key={key} data-active={view === key}>
                            <figcaption>{title}</figcaption>
                            {station === 'tech' ? (
                                <>
                                    <div className={styles.visualComparison}>
                                        <section className={styles.visualCard}>
                                            <strong>Макет заказчика</strong>
                                            <ConstructorPreview
                                                unit={unit}
                                                title={title}
                                                view={key}
                                                src={src}
                                                garmentWidth={garmentWidth}
                                                garmentHeight={garmentHeight}
                                                decorations={decorations}
                                            />
                                            <small>
                                                Вид из конструктора с
                                                нанесениями заказчика
                                            </small>
                                        </section>
                                        <section className={styles.visualCard}>
                                            <strong>Наложение на лекало</strong>
                                            <div
                                                className={
                                                    styles.patternPreview
                                                }
                                            >
                                                <PiStack aria-hidden />
                                                <span>
                                                    Здесь появится
                                                    производственный макет
                                                    поверх лекала
                                                </span>
                                            </div>
                                            <small>
                                                Добавим после подготовки
                                                наложения
                                            </small>
                                        </section>
                                    </div>
                                    <div className={styles.patternActions}>
                                        {patternFiles.length ? (
                                            patternFiles.map((file, index) => (
                                                <button
                                                    type="button"
                                                    key={file.id}
                                                    disabled={
                                                        openingFile !== null
                                                    }
                                                    onClick={() =>
                                                        void openPattern(
                                                            file.id,
                                                        )
                                                    }
                                                >
                                                    <PiArrowSquareOut aria-hidden />
                                                    {openingFile === file.id
                                                        ? 'Открываем…'
                                                        : patternFiles.length ===
                                                            1
                                                          ? 'Открыть оригинал лекала'
                                                          : `Открыть оригинал лекала ${index + 1}`}
                                                </button>
                                            ))
                                        ) : (
                                            <button type="button" disabled>
                                                Оригинал лекала не прикреплён
                                            </button>
                                        )}
                                        {fileError && (
                                            <p
                                                className={styles.error}
                                                role="alert"
                                            >
                                                {fileError}
                                            </p>
                                        )}
                                    </div>
                                </>
                            ) : (
                                <ConstructorPreview
                                    unit={unit}
                                    title={title}
                                    view={key}
                                    src={src}
                                    garmentWidth={garmentWidth}
                                    garmentHeight={garmentHeight}
                                    decorations={decorations}
                                />
                            )}
                            {station !== 'tech' && (
                                <small>
                                    Макет из конструктора: основа и нанесения в
                                    сохранённых координатах.
                                </small>
                            )}
                        </figure>
                    );
                })}
            </div>
        </div>
    );
}
