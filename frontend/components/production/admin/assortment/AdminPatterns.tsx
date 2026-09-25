'use client';

import { useMemo, useState, type FormEvent } from 'react';
import {
    PiCaretDown,
    PiCheck,
    PiPlus,
    PiUploadSimple,
} from 'react-icons/pi';
import { useAssortmentResource } from '@/hooks/production/useAssortmentResource';
import {
    saveAssortment,
    uploadAssortmentMedia,
} from '@/lib/api/productionAssortment';
import { compactDecimal } from '@/lib/production/numbers';
import type {
    GarmentModel,
    GarmentSize,
    Pattern,
    ReferencePage,
} from '@/lib/production/assortmentTypes';
import { AdminFilters } from '../AdminFilters';
import {
    AssortmentDialog,
    AssortmentFeedback,
    FileUploadStatus,
    idleFileUploadStatus,
    type FileUploadStatusValue,
} from './AssortmentDialog';
import styles from '../ProductionAdmin.module.css';

type SleeveVariant = Pattern['sleeve_variant'];
type MeasurementKey = 'width_cm' | 'length_cm';
type PatternForm = Omit<Pattern, 'id' | 'version' | 'grid_key' | 'name'> & {
    id?: number;
    version?: number;
    filename?: string;
};

type MeasurementRange = { min: string | null; max: string | null };

const variantLabel: Record<SleeveVariant, string> = {
    standard: 'Стандартный рукав',
    height: 'Рукав по росту',
};

const variantShortLabel: Record<SleeveVariant, string> = {
    standard: 'Стандарт',
    height: 'По росту',
};

const sizeVariants = (size?: GarmentSize): SleeveVariant[] => {
    if (!size) return ['standard'];
    const variants: SleeveVariant[] = [];
    if (size.allow_standard_sleeve) variants.push('standard');
    if (size.allow_height_sleeve) variants.push('height');
    return variants.length ? variants : ['standard'];
};

const rangeValues = (minimum: string | null, maximum: string | null) => {
    if (minimum === null || maximum === null) return [];
    const start = Number(minimum);
    const end = Number(maximum);
    if (!Number.isFinite(start) || !Number.isFinite(end) || start > end) return [];
    const values: string[] = [];
    for (let value = start; value <= end + 0.001; value += 2) {
        values.push(compactDecimal(value.toFixed(2)));
    }
    return values;
};

const slotKey = (
    modelId: number,
    sizeId: number,
    width: string,
    length: string,
    sleeveVariant: SleeveVariant,
) =>
    [
        modelId,
        sizeId,
        Number(width).toFixed(2),
        Number(length).toFixed(2),
        sleeveVariant,
    ].join(':');

const generatedCode = (
    model: GarmentModel,
    size: GarmentSize,
    width: string,
    length: string,
    sleeveVariant: SleeveVariant,
) => {
    const part = (value: string) => compactDecimal(value).replace('.', '_');
    const suffix = `-${size.code}-${part(width)}X${part(length)}-${
        sleeveVariant === 'height' ? 'H' : 'S'
    }`;
    return `${`PAT-${model.code}`.slice(0, 64 - suffix.length)}${suffix}`;
};

function PatternMeasurement({
    label,
    field,
    value,
    range,
    onChange,
}: {
    label: string;
    field: MeasurementKey;
    value: string;
    range: MeasurementRange;
    onChange: (field: MeasurementKey, value: string) => void;
}) {
    const available = range.min !== null && range.max !== null;
    return (
        <section className={styles.patternMeasurement} data-enabled={available}>
            <div className={styles.patternMeasurementHeading}>
                <div>
                    <strong>{label}</strong>
                    <small>
                        {available
                            ? `${compactDecimal(range.min)}–${compactDecimal(range.max)} см`
                            : 'Диапазон не задан для размера'}
                    </small>
                </div>
                <output htmlFor={`pattern-${field}`}>
                    {value ? `${compactDecimal(value)} см` : '—'}
                </output>
            </div>
            {available && (
                <div className={styles.patternRangeControl}>
                    <input
                        id={`pattern-${field}`}
                        type="range"
                        min={range.min ?? undefined}
                        max={range.max ?? undefined}
                        step="2"
                        value={value}
                        aria-label={`${label}, сантиметры`}
                        onChange={(event) => onChange(field, event.target.value)}
                    />
                    <div className={styles.patternRangeEnds} aria-hidden="true">
                        <span>{compactDecimal(range.min ?? '')}</span>
                        <span>{compactDecimal(range.max ?? '')}</span>
                    </div>
                </div>
            )}
        </section>
    );
}

const emptyPattern = (
    model?: GarmentModel,
    size?: GarmentSize,
    width?: string,
    length?: string,
    sleeveVariant?: SleeveVariant,
): PatternForm => {
    const selectedSize = size ?? model?.sizes[0];
    const variant = sleeveVariant ?? sizeVariants(selectedSize)[0];
    const selectedWidth = width ?? selectedSize?.min_width_cm ?? '';
    const selectedLength = length ?? selectedSize?.min_length_cm ?? '';
    return {
        code:
            model && selectedSize && selectedWidth && selectedLength
                ? generatedCode(
                      model,
                      selectedSize,
                      selectedWidth,
                      selectedLength,
                      variant,
                  )
                : '',
        garment_model_id: model?.id ?? 0,
        garment_size_id: selectedSize?.id ?? 0,
        media_object_id: 0,
        sleeve_variant: variant,
        width_cm: selectedWidth,
        length_cm: selectedLength,
        is_active: true,
    };
};

const patternEditor = (pattern: Pattern): PatternForm => ({
    ...pattern,
    width_cm: compactDecimal(pattern.width_cm),
    length_cm: compactDecimal(pattern.length_cm),
});

export function AdminPatterns() {
    const patternsResource = useAssortmentResource<Pattern[]>('patterns');
    const modelsResource =
        useAssortmentResource<ReferencePage<GarmentModel>>('models');
    const [modelFilter, setModelFilter] = useState(0);
    const [activityFilter, setActivityFilter] = useState('');
    const [sorting, setSorting] = useState('model:asc');
    const [query, setQuery] = useState('');
    const [editor, setEditor] = useState<PatternForm | null>(null);
    const [saving, setSaving] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] =
        useState<FileUploadStatusValue>(idleFileUploadStatus);
    const [formError, setFormError] = useState('');
    const models = useMemo(
        () => modelsResource.data?.items ?? [],
        [modelsResource.data],
    );
    const allPatterns = useMemo(
        () => patternsResource.data ?? [],
        [patternsResource.data],
    );
    const patternsBySlot = useMemo(() => {
        const result = new Map<string, Pattern>();
        for (const pattern of allPatterns) {
            result.set(
                slotKey(
                    pattern.garment_model_id,
                    pattern.garment_size_id,
                    pattern.width_cm,
                    pattern.length_cm,
                    pattern.sleeve_variant,
                ),
                pattern,
            );
        }
        return result;
    }, [allPatterns]);
    const visibleModels = useMemo(() => {
        const needle = query.trim().toLowerCase();
        const result = models.filter((model) => {
            if (modelFilter && model.id !== modelFilter) return false;
            const modelPatterns = allPatterns.filter(
                (pattern) => pattern.garment_model_id === model.id,
            );
            if (
                activityFilter &&
                !modelPatterns.some(
                    (pattern) =>
                        pattern.is_active === (activityFilter === 'active'),
                )
            ) {
                return false;
            }
            return (
                !needle ||
                `${model.name} ${model.code}`.toLowerCase().includes(needle) ||
                modelPatterns.some((pattern) =>
                    pattern.code.toLowerCase().includes(needle),
                )
            );
        });
        const direction = sorting.endsWith(':desc') ? -1 : 1;
        return [...result].sort((left, right) => {
            const leftValue = sorting.startsWith('code') ? left.code : left.name;
            const rightValue = sorting.startsWith('code') ? right.code : right.name;
            return (
                leftValue.localeCompare(rightValue, 'ru', { numeric: true }) *
                direction
            );
        });
    }, [activityFilter, allPatterns, modelFilter, models, query, sorting]);

    const openNewPattern = (
        model: GarmentModel,
        size?: GarmentSize,
        width?: string,
        length?: string,
        sleeveVariant?: SleeveVariant,
    ) => {
        setUploadStatus(idleFileUploadStatus);
        setFormError('');
        setEditor(emptyPattern(model, size, width, length, sleeveVariant));
    };
    const openPattern = (pattern: Pattern) => {
        setUploadStatus({
            state: 'success',
            message: 'Файл лекала уже загружен',
        });
        setFormError('');
        setEditor(patternEditor(pattern));
    };
    const submit = async (event: FormEvent) => {
        event.preventDefault();
        if (!editor) return;
        if (!editor.media_object_id) {
            setFormError('Загрузите файл лекала.');
            return;
        }
        setSaving(true);
        setFormError('');
        try {
            await saveAssortment(
                editor.id ? `patterns/${editor.id}` : 'patterns',
                editor.id ? 'PUT' : 'POST',
                {
                    code: editor.code,
                    garment_model_id: editor.garment_model_id,
                    garment_size_id: editor.garment_size_id,
                    media_object_id: editor.media_object_id,
                    name: editor.code,
                    sleeve_variant: editor.sleeve_variant,
                    width_cm: Number(editor.width_cm),
                    length_cm: Number(editor.length_cm),
                    is_active: editor.is_active,
                    ...(editor.id ? { expected_version: editor.version } : {}),
                },
            );
            setEditor(null);
            patternsResource.reload();
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось сохранить лекало',
            );
        } finally {
            setSaving(false);
        }
    };

    return (
        <section aria-busy={patternsResource.loading || modelsResource.loading}>
            <div className={styles.assortmentHeading}>
                <div>
                    <h3>Лекала по моделям</h3>
                    <p className={styles.muted}>
                        В каждой клетке видно, какие файлы загружены для ширины и
                        длины изделия.
                    </p>
                </div>
                <button
                    disabled={!models.length}
                    onClick={() => models[0] && openNewPattern(models[0])}
                >
                    <PiPlus aria-hidden /> Добавить лекало
                </button>
            </div>
            <div className={styles.assortmentFilters}>
                <label className={styles.assortmentSearch}>
                    Поиск по модели или коду лекала
                    <input
                        type="search"
                        value={query}
                        placeholder="Модель или PAT-HOODIE-M"
                        onChange={(event) => setQuery(event.target.value)}
                    />
                </label>
                <AdminFilters
                    groups={[
                        {
                            key: 'model',
                            label: 'Модель',
                            options: [
                                ['0', 'Все модели'],
                                ...models.map(
                                    (model) =>
                                        [String(model.id), model.name] as const,
                                ),
                            ],
                        },
                        {
                            key: 'activity',
                            label: 'Лекала',
                            options: [
                                ['', 'Все состояния'],
                                ['active', 'Есть активные'],
                                ['hidden', 'Есть скрытые'],
                            ],
                        },
                        {
                            key: 'sorting',
                            label: 'Сортировка',
                            options: [
                                ['model:asc', 'Модель: А–Я'],
                                ['model:desc', 'Модель: Я–А'],
                                ['code:asc', 'Код: А–Я'],
                                ['code:desc', 'Код: Я–А'],
                            ],
                        },
                    ]}
                    values={{
                        model: String(modelFilter),
                        activity: activityFilter,
                        sorting,
                    }}
                    defaults={{ model: '0', activity: '', sorting: 'model:asc' }}
                    onApply={(values) => {
                        setModelFilter(Number(values.model));
                        setActivityFilter(values.activity);
                        setSorting(values.sorting);
                    }}
                />
            </div>
            <AssortmentFeedback
                loading={patternsResource.loading || modelsResource.loading}
                error={patternsResource.error || modelsResource.error}
                empty={
                    !patternsResource.loading &&
                    !modelsResource.loading &&
                    visibleModels.length === 0
                }
            />
            {visibleModels.length > 0 && (
                <div className={styles.patternCoverageList}>
                    {visibleModels.map((model) => {
                        let required = 0;
                        let uploaded = 0;
                        for (const size of model.sizes) {
                            const widths = rangeValues(
                                size.min_width_cm,
                                size.max_width_cm,
                            );
                            const lengths = rangeValues(
                                size.min_length_cm,
                                size.max_length_cm,
                            );
                            for (const width of widths) {
                                for (const length of lengths) {
                                    for (const variant of sizeVariants(size)) {
                                        required += 1;
                                        if (
                                            patternsBySlot.has(
                                                slotKey(
                                                    model.id,
                                                    size.id ?? 0,
                                                    width,
                                                    length,
                                                    variant,
                                                ),
                                            )
                                        ) {
                                            uploaded += 1;
                                        }
                                    }
                                }
                            }
                        }
                        return (
                            <details
                                className={styles.patternModelCoverage}
                                key={model.id}
                                open={visibleModels.length === 1}
                            >
                                <summary>
                                    <div>
                                        <strong>{model.name}</strong>
                                        <small>{model.code}</small>
                                    </div>
                                    <div className={styles.patternCoverageMeta}>
                                        <span data-complete={required > 0 && uploaded === required}>
                                            {uploaded} из {required}
                                        </span>
                                        <small>лекал загружено</small>
                                        <PiCaretDown aria-hidden />
                                    </div>
                                </summary>
                                <div className={styles.patternSizeList}>
                                    {model.sizes.map((size) => {
                                        const widths = rangeValues(
                                            size.min_width_cm,
                                            size.max_width_cm,
                                        );
                                        const lengths = rangeValues(
                                            size.min_length_cm,
                                            size.max_length_cm,
                                        );
                                        const variants = sizeVariants(size);
                                        return (
                                            <section
                                                className={styles.patternSizeCoverage}
                                                key={size.id ?? size.code}
                                            >
                                                <div className={styles.patternSizeSummary}>
                                                    <div>
                                                        <strong>Размер {size.code}</strong>
                                                        <small>
                                                            {variants
                                                                .map(
                                                                    (variant) =>
                                                                        variantShortLabel[variant],
                                                                )
                                                                .join(' · ')}
                                                        </small>
                                                    </div>
                                                    <button
                                                        type="button"
                                                        onClick={() =>
                                                            openNewPattern(model, size)
                                                        }
                                                    >
                                                        <PiPlus aria-hidden /> Добавить
                                                    </button>
                                                </div>
                                                {!widths.length || !lengths.length ? (
                                                    <p className={styles.patternEmptyGrid}>
                                                        В модели не заполнены диапазоны
                                                        ширины и длины для этого размера.
                                                    </p>
                                                ) : (
                                                    <div
                                                        className={styles.patternCoverageScroll}
                                                        tabIndex={0}
                                                    >
                                                        <table className={styles.patternCoverageTable}>
                                                            <thead>
                                                                <tr>
                                                                    <th scope="col">
                                                                        Длина ↓ / Ширина →
                                                                    </th>
                                                                    {widths.map((width) => (
                                                                        <th scope="col" key={width}>
                                                                            {width} см
                                                                        </th>
                                                                    ))}
                                                                </tr>
                                                            </thead>
                                                            <tbody>
                                                                {lengths.map((length) => (
                                                                    <tr key={length}>
                                                                        <th scope="row">
                                                                            {length} см
                                                                        </th>
                                                                        {widths.map((width) => (
                                                                            <td key={width}>
                                                                                <div className={styles.patternSlot}>
                                                                                    {variants.map(
                                                                                        (variant) => {
                                                                                            const pattern = patternsBySlot.get(
                                                                                                slotKey(
                                                                                                    model.id,
                                                                                                    size.id ?? 0,
                                                                                                    width,
                                                                                                    length,
                                                                                                    variant,
                                                                                                ),
                                                                                            );
                                                                                            const state = pattern
                                                                                                ? pattern.is_active
                                                                                                    ? 'ready'
                                                                                                    : 'hidden'
                                                                                                : 'missing';
                                                                                            return (
                                                                                                <button
                                                                                                    type="button"
                                                                                                    className={styles.patternVariantSlot}
                                                                                                    data-state={state}
                                                                                                    key={variant}
                                                                                                    title={
                                                                                                        pattern
                                                                                                            ? `${variantLabel[variant]} · ${pattern.code}`
                                                                                                            : `${variantLabel[variant]} · файл не загружен`
                                                                                                    }
                                                                                                    onClick={() =>
                                                                                                        pattern
                                                                                                            ? openPattern(pattern)
                                                                                                            : openNewPattern(
                                                                                                                  model,
                                                                                                                  size,
                                                                                                                  width,
                                                                                                                  length,
                                                                                                                  variant,
                                                                                                              )
                                                                                                    }
                                                                                                >
                                                                                                    {pattern ? (
                                                                                                        <PiCheck aria-hidden />
                                                                                                    ) : (
                                                                                                        <PiPlus aria-hidden />
                                                                                                    )}
                                                                                                    <span>{variantShortLabel[variant]}</span>
                                                                                                </button>
                                                                                            );
                                                                                        },
                                                                                    )}
                                                                                </div>
                                                                            </td>
                                                                        ))}
                                                                    </tr>
                                                                ))}
                                                            </tbody>
                                                        </table>
                                                    </div>
                                                )}
                                            </section>
                                        );
                                    })}
                                </div>
                            </details>
                        );
                    })}
                    <div className={styles.patternSlotLegend}>
                        <span data-state="ready">Загружено</span>
                        <span data-state="missing">Не загружено</span>
                        <span data-state="hidden">Скрыто</span>
                    </div>
                </div>
            )}
            {editor && (
                <AssortmentDialog
                    title={editor.id ? 'Изменить лекало' : 'Новое лекало'}
                    headerActions={
                        <details className={styles.patternStatusMenu}>
                            <summary>
                                <span
                                    className={styles.patternStatusDot}
                                    data-active={editor.is_active}
                                />
                                {editor.is_active ? 'Активно' : 'Неактивно'}
                                <PiCaretDown aria-hidden />
                            </summary>
                            <div role="menu">
                                {([
                                    [true, 'Активно'],
                                    [false, 'Неактивно'],
                                ] as const).map(([active, label]) => (
                                    <button
                                        type="button"
                                        role="menuitemradio"
                                        aria-checked={editor.is_active === active}
                                        key={String(active)}
                                        onClick={(event) => {
                                            setEditor({ ...editor, is_active: active });
                                            event.currentTarget
                                                .closest('details')
                                                ?.removeAttribute('open');
                                        }}
                                    >
                                        <span>{label}</span>
                                        {editor.is_active === active && (
                                            <PiCheck aria-hidden />
                                        )}
                                    </button>
                                ))}
                            </div>
                        </details>
                    }
                    onClose={() => setEditor(null)}
                >
                    <form className={styles.patternForm} onSubmit={submit}>
                        <div className={styles.patternIdentityGrid}>
                            <label className={styles.fullField}>
                                Код лекала
                                <input
                                    required
                                    maxLength={64}
                                    value={editor.code}
                                    placeholder="PAT-HOODIE-M-60X72-S"
                                    onChange={(event) =>
                                        setEditor({
                                            ...editor,
                                            code: event.target.value.toUpperCase(),
                                        })
                                    }
                                />
                                <small>Латиница, цифры, дефис или подчёркивание</small>
                            </label>
                            <label>
                                Модель
                                <select
                                    required
                                    disabled={Boolean(editor.id)}
                                    value={editor.garment_model_id || ''}
                                    onChange={(event) => {
                                        const model = models.find(
                                            (item) =>
                                                item.id === Number(event.target.value),
                                        );
                                        setEditor(emptyPattern(model));
                                    }}
                                >
                                    <option value="">Выберите модель</option>
                                    {models.map((model) => (
                                        <option key={model.id} value={model.id}>
                                            {model.name}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label>
                                Размер
                                <select
                                    required
                                    disabled={Boolean(editor.id)}
                                    value={editor.garment_size_id || ''}
                                    onChange={(event) => {
                                        const model = models.find(
                                            (item) =>
                                                item.id === editor.garment_model_id,
                                        );
                                        const size = model?.sizes.find(
                                            (item) =>
                                                item.id === Number(event.target.value),
                                        );
                                        setEditor(emptyPattern(model, size));
                                    }}
                                >
                                    <option value="">Выберите размер</option>
                                    {(
                                        models.find(
                                            (model) =>
                                                model.id === editor.garment_model_id,
                                        )?.sizes ?? []
                                    ).map((size) => (
                                        <option key={size.id} value={size.id}>
                                            {size.code}
                                        </option>
                                    ))}
                                </select>
                            </label>
                        </div>
                        {(() => {
                            const model = models.find(
                                (item) => item.id === editor.garment_model_id,
                            );
                            const size = model?.sizes.find(
                                (item) => item.id === editor.garment_size_id,
                            );
                            const variants = sizeVariants(size);
                            const updateMeasurement = (
                                field: MeasurementKey,
                                value: string,
                            ) => {
                                const next = { ...editor, [field]: value };
                                if (!editor.id && model && size) {
                                    next.code = generatedCode(
                                        model,
                                        size,
                                        field === 'width_cm'
                                            ? value
                                            : editor.width_cm,
                                        field === 'length_cm'
                                            ? value
                                            : editor.length_cm,
                                        editor.sleeve_variant,
                                    );
                                }
                                setEditor(next);
                            };
                            return (
                                <>
                                    <fieldset className={styles.patternVariantField}>
                                        <legend>Вариант лекала</legend>
                                        <div className={styles.squareChoiceGrid}>
                                            {variants.map((variant) => (
                                                <button
                                                    type="button"
                                                    key={variant}
                                                    data-selected={
                                                        editor.sleeve_variant === variant
                                                    }
                                                    aria-pressed={
                                                        editor.sleeve_variant === variant
                                                    }
                                                    onClick={() => {
                                                        const next = {
                                                            ...editor,
                                                            sleeve_variant: variant,
                                                        };
                                                        if (!editor.id && model && size) {
                                                            next.code = generatedCode(
                                                                model,
                                                                size,
                                                                editor.width_cm,
                                                                editor.length_cm,
                                                                variant,
                                                            );
                                                        }
                                                        setEditor(next);
                                                    }}
                                                >
                                                    <PiCheck aria-hidden />
                                                    <strong>{variantLabel[variant]}</strong>
                                                    <small>
                                                        {variant === 'height'
                                                            ? 'Файл для рукава, выбранного по росту'
                                                            : 'Файл со стандартным рукавом'}
                                                    </small>
                                                </button>
                                            ))}
                                        </div>
                                    </fieldset>
                                    <div className={styles.patternMeasurements}>
                                        <PatternMeasurement
                                            label="Ширина изделия"
                                            field="width_cm"
                                            value={editor.width_cm}
                                            range={{
                                                min: size?.min_width_cm ?? null,
                                                max: size?.max_width_cm ?? null,
                                            }}
                                            onChange={updateMeasurement}
                                        />
                                        <PatternMeasurement
                                            label="Длина изделия"
                                            field="length_cm"
                                            value={editor.length_cm}
                                            range={{
                                                min: size?.min_length_cm ?? null,
                                                max: size?.max_length_cm ?? null,
                                            }}
                                            onChange={updateMeasurement}
                                        />
                                    </div>
                                </>
                            );
                        })()}
                        <div className={styles.patternFileField}>
                            <span>Файл лекала</span>
                            <label className={styles.patternFilePicker}>
                                <input
                                    type="file"
                                    accept="application/pdf,image/jpeg,image/png,image/webp"
                                    disabled={uploading}
                                    onChange={async (event) => {
                                        const file = event.target.files?.[0];
                                        if (!file) return;
                                        setUploading(true);
                                        setUploadStatus({
                                            state: 'uploading',
                                            fileName: file.name,
                                        });
                                        setFormError('');
                                        try {
                                            const uploaded =
                                                await uploadAssortmentMedia(
                                                    file,
                                                    'pattern',
                                                );
                                            setEditor((current) =>
                                                current
                                                    ? {
                                                          ...current,
                                                          media_object_id:
                                                              uploaded.id,
                                                          filename:
                                                              uploaded.filename ??
                                                              file.name,
                                                      }
                                                    : current,
                                            );
                                            setUploadStatus({
                                                state: 'success',
                                                fileName: file.name,
                                            });
                                        } catch (reason) {
                                            const message =
                                                reason instanceof Error
                                                    ? reason.message
                                                    : 'Не удалось загрузить файл';
                                            setFormError(message);
                                            setUploadStatus({
                                                state: 'error',
                                                fileName: file.name,
                                                message,
                                            });
                                        } finally {
                                            setUploading(false);
                                        }
                                    }}
                                />
                                <PiUploadSimple aria-hidden />
                                <span>
                                    {editor.filename ??
                                        (editor.media_object_id
                                            ? `Медиа №${editor.media_object_id}`
                                            : 'PDF, JPEG, PNG или WebP')}
                                </span>
                            </label>
                            <FileUploadStatus value={uploadStatus} />
                        </div>
                        {formError && (
                            <p className={styles.error} role="alert">
                                {formError}
                            </p>
                        )}
                        <div className={styles.editorActions}>
                            <button type="button" onClick={() => setEditor(null)}>
                                Отмена
                            </button>
                            <button
                                className={styles.primaryButton}
                                disabled={saving || uploading}
                            >
                                {saving ? 'Сохраняем…' : 'Сохранить'}
                            </button>
                        </div>
                    </form>
                </AssortmentDialog>
            )}
        </section>
    );
}
