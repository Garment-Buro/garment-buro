'use client';

import { useMemo, useState, type FormEvent } from 'react';
import {
    PiArrowRight,
    PiCaretDown,
    PiCheck,
    PiImage,
    PiPencilSimple,
    PiPlus,
    PiRuler,
    PiTShirt,
    PiTrash,
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
    GarmentModelCategory,
    GarmentSize,
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

const emptySize = (sortOrder: number): GarmentSize => ({
    code: '',
    sort_order: sortOrder,
    base_price: '0',
    base_length_cm: null,
    base_width_cm: null,
    min_height_cm: null,
    max_height_cm: null,
    min_length_cm: null,
    max_length_cm: null,
    min_width_cm: null,
    max_width_cm: null,
    min_sleeve_length_cm: null,
    max_sleeve_length_cm: null,
    allow_standard_sleeve: true,
    allow_height_sleeve: true,
    extra_width_price_per_cm: null,
});

type ModelForm = Omit<
    GarmentModel,
    'id' | 'version' | 'catalog_product_ids' | 'published_tech_card'
> & { id?: number; version?: number };

type ModelEditor = ModelForm & { size_chart_url?: string | null };

type CategoryEditor = {
    id?: number;
    version?: number;
    name: string;
    is_active: boolean;
};

const emptyModel = (categoryId: number | null): ModelForm => ({
    category_id: categoryId,
    code: '',
    name: '',
    description: null,
    base_size_code: null,
    fit_model_name: null,
    fit_model_height_cm: null,
    base_weight_g: null,
    size_chart_media_object_id: null,
    is_active: true,
    sizes: [emptySize(0)],
});

const optionalNumber = (value: string | null | undefined) =>
    value == null || value === '' ? null : Number(value);

const compactNullableDecimal = (value: string | null | undefined) =>
    value == null ? null : compactDecimal(value);

const compactSize = (size: GarmentSize): GarmentSize => ({
    ...size,
    base_price: compactDecimal(size.base_price),
    base_length_cm: compactNullableDecimal(size.base_length_cm),
    base_width_cm: compactNullableDecimal(size.base_width_cm),
    min_height_cm: compactNullableDecimal(size.min_height_cm),
    max_height_cm: compactNullableDecimal(size.max_height_cm),
    min_length_cm: compactNullableDecimal(size.min_length_cm),
    max_length_cm: compactNullableDecimal(size.max_length_cm),
    min_width_cm: compactNullableDecimal(size.min_width_cm),
    max_width_cm: compactNullableDecimal(size.max_width_cm),
    min_sleeve_length_cm: compactNullableDecimal(size.min_sleeve_length_cm),
    max_sleeve_length_cm: compactNullableDecimal(size.max_sleeve_length_cm),
    extra_width_price_per_cm: compactNullableDecimal(
        size.extra_width_price_per_cm,
    ),
});

type SizeRangeField =
    | 'min_width_cm'
    | 'max_width_cm'
    | 'min_length_cm'
    | 'max_length_cm'
    | 'min_height_cm'
    | 'max_height_cm';

function SizeRangeEditor({
    label,
    size,
    minimum,
    maximum,
    onChange,
}: {
    label: string;
    size: GarmentSize;
    minimum: SizeRangeField;
    maximum: SizeRangeField;
    onChange: (field: SizeRangeField, value: string) => void;
}) {
    return (
        <section className={styles.sizeRangeCard}>
            <div className={styles.sizeRangeHeading}>
                <PiRuler aria-hidden />
                <strong>{label}</strong>
            </div>
            <div className={styles.sizeRangeInputs}>
                <label>
                    <span>От</span>
                    <input
                        type="number"
                        min="0"
                        step="2"
                        inputMode="decimal"
                        value={size[minimum] ?? ''}
                        placeholder="—"
                        onChange={(event) => onChange(minimum, event.target.value)}
                    />
                </label>
                <PiArrowRight aria-hidden />
                <label>
                    <span>До</span>
                    <input
                        type="number"
                        min="0"
                        step="2"
                        inputMode="decimal"
                        value={size[maximum] ?? ''}
                        placeholder="—"
                        onChange={(event) => onChange(maximum, event.target.value)}
                    />
                </label>
                <span className={styles.sizeRangeUnit}>см</span>
            </div>
        </section>
    );
}

const sizeSummary = (size: GarmentSize) => {
    const base =
        size.base_width_cm && size.base_length_cm
            ? `База ${Number(size.base_width_cm)} × ${Number(size.base_length_cm)} см`
            : 'База не задана';
    const width =
        size.min_width_cm && size.max_width_cm
            ? `${Number(size.min_width_cm)}–${Number(size.max_width_cm)} см`
            : 'Ширина не задана';
    const length =
        size.min_length_cm && size.max_length_cm
            ? `${Number(size.min_length_cm)}–${Number(size.max_length_cm)} см`
            : 'Длина не задана';
    return `${base} · ${width} · ${length}`;
};

export function AdminModels() {
    const { data, loading, error, reload } =
        useAssortmentResource<ReferencePage<GarmentModel>>('models');
    const categories =
        useAssortmentResource<GarmentModelCategory[]>('model-categories');
    const [search, setSearch] = useState('');
    const [categoryFilter, setCategoryFilter] = useState<number | null>(null);
    const [activityFilter, setActivityFilter] = useState('');
    const [sorting, setSorting] = useState('name:asc');
    const [editor, setEditor] = useState<ModelEditor | null>(null);
    const [categoryEditor, setCategoryEditor] =
        useState<CategoryEditor | null>(null);
    const [activeSizeIndex, setActiveSizeIndex] = useState(0);
    const [saving, setSaving] = useState(false);
    const [formError, setFormError] = useState('');
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] =
        useState<FileUploadStatusValue>(idleFileUploadStatus);
    const models = useMemo(() => {
        const query = search.trim().toLocaleLowerCase('ru');
        const filtered = (data?.items ?? []).filter(
            (model) =>
                (categoryFilter == null ||
                    model.category_id === categoryFilter) &&
                (!activityFilter ||
                    model.is_active === (activityFilter === 'active')) &&
                (!query ||
                    `${model.name} ${model.code}`
                        .toLocaleLowerCase('ru')
                        .includes(query)),
        );
        const [field, direction] = sorting.split(':');
        return [...filtered].sort((left, right) => {
            const values: Record<string, [string | number, string | number]> = {
                name: [left.name, right.name],
                code: [left.code, right.code],
                sizes: [left.sizes.length, right.sizes.length],
                products: [
                    left.catalog_product_ids.length,
                    right.catalog_product_ids.length,
                ],
            };
            const [a, b] = values[field] ?? values.name;
            const result =
                typeof a === 'number' && typeof b === 'number'
                    ? a - b
                    : String(a).localeCompare(String(b), 'ru');
            return direction === 'desc' ? -result : result;
        });
    }, [activityFilter, categoryFilter, data, search, sorting]);
    const activeSize = editor?.sizes[activeSizeIndex] ?? null;
    const categoryName = (categoryId: number | null) =>
        categories.data?.find((category) => category.id === categoryId)?.name ??
        'Без категории';

    const openEditor = (model?: GarmentModel) => {
        setActiveSizeIndex(0);
        setUploadStatus(
            model?.size_chart_media_object_id
                ? {
                      state: 'success',
                      message: 'Таблица размеров уже загружена',
                  }
                : idleFileUploadStatus,
        );
        setEditor(
            model
                ? {
                      ...model,
                      size_chart_url: model.size_chart_media_object_id
                          ? `/production/admin/assortment/media/public/${model.size_chart_media_object_id}`
                          : null,
                      fit_model_height_cm: compactNullableDecimal(
                          model.fit_model_height_cm,
                      ),
                      base_weight_g: compactNullableDecimal(model.base_weight_g),
                      sizes: model.sizes.map(compactSize),
                  }
                : emptyModel(categories.data?.find((item) => item.is_active)?.id ?? null),
        );
    };

    const updateSize = (
        index: number,
        field: keyof GarmentSize,
        value: string,
    ) => {
        setEditor((current) => {
            if (!current) return current;
            const sizes = [...current.sizes];
            sizes[index] = {
                ...sizes[index],
                [field]: field === 'sort_order' ? Number(value) : value || null,
            };
            return { ...current, sizes };
        });
    };

    const submit = async (event: FormEvent) => {
        event.preventDefault();
        if (!editor) return;
        setSaving(true);
        setFormError('');
        const payload = {
            category_id: editor.category_id,
            code: editor.code,
            name: editor.name,
            description: editor.description,
            base_size_code: editor.base_size_code,
            fit_model_name: editor.fit_model_name,
            fit_model_height_cm: optionalNumber(editor.fit_model_height_cm),
            base_weight_g: optionalNumber(editor.base_weight_g),
            size_chart_media_object_id: editor.size_chart_media_object_id,
            is_active: editor.is_active,
            sizes: editor.sizes.map((size, index) => ({
                code: size.code,
                sort_order: index,
                base_price: Number(size.base_price || 0),
                base_length_cm: optionalNumber(size.base_length_cm),
                base_width_cm: optionalNumber(size.base_width_cm),
                min_height_cm: optionalNumber(size.min_height_cm),
                max_height_cm: optionalNumber(size.max_height_cm),
                min_length_cm: optionalNumber(size.min_length_cm),
                max_length_cm: optionalNumber(size.max_length_cm),
                min_width_cm: optionalNumber(size.min_width_cm),
                max_width_cm: optionalNumber(size.max_width_cm),
                min_sleeve_length_cm: optionalNumber(
                    size.min_sleeve_length_cm,
                ),
                max_sleeve_length_cm: optionalNumber(
                    size.max_sleeve_length_cm,
                ),
                allow_standard_sleeve: size.allow_standard_sleeve,
                allow_height_sleeve: size.allow_height_sleeve,
                extra_width_price_per_cm: optionalNumber(
                    size.extra_width_price_per_cm,
                ),
                currency: 'RUB',
            })),
            ...(editor.id ? { expected_version: editor.version } : {}),
        };
        try {
            await saveAssortment(
                editor.id ? `models/${editor.id}` : 'models',
                editor.id ? 'PUT' : 'POST',
                payload,
            );
            setEditor(null);
            reload();
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось сохранить модель',
            );
        } finally {
            setSaving(false);
        }
    };

    const submitCategory = async (event: FormEvent) => {
        event.preventDefault();
        if (!categoryEditor) return;
        setSaving(true);
        setFormError('');
        try {
            await saveAssortment(
                categoryEditor.id
                    ? `model-categories/${categoryEditor.id}`
                    : 'model-categories',
                categoryEditor.id ? 'PUT' : 'POST',
                {
                    name: categoryEditor.name,
                    is_active: categoryEditor.is_active,
                    ...(categoryEditor.id
                        ? { expected_version: categoryEditor.version }
                        : {}),
                },
            );
            setCategoryEditor(null);
            categories.reload();
            reload();
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось сохранить категорию',
            );
        } finally {
            setSaving(false);
        }
    };

    return (
        <section aria-busy={loading || categories.loading}>
            <div className={styles.assortmentHeading}>
                <div>
                    <h3>Модели изделий</h3>
                    <p className={styles.muted}>
                        Размеры, диапазоны мерок, вес и таблица размеров для сайта.
                    </p>
                </div>
                <div className={styles.headingActions}>
                    <button
                        onClick={() =>
                            setCategoryEditor({
                                name: '',
                                is_active: true,
                            })
                        }
                    >
                        <PiPlus aria-hidden /> Категория
                    </button>
                    <button onClick={() => openEditor()}>
                        <PiPlus aria-hidden /> Добавить модель
                    </button>
                </div>
            </div>
            <div
                className={styles.assortmentCategoryGrid}
                aria-label="Категории моделей"
            >
                {(categories.data ?? []).map((category) => {
                        const count = (data?.items ?? []).filter(
                            (model) => model.category_id === category.id,
                        ).length;
                        return (
                            <article
                                key={category.id}
                                data-selected={categoryFilter === category.id}
                                data-active={category.is_active}
                            >
                                <button
                                    type="button"
                                    className={styles.assortmentCategorySelect}
                                    aria-pressed={categoryFilter === category.id}
                                    onClick={() =>
                                        setCategoryFilter((current) =>
                                            current === category.id
                                                ? null
                                                : category.id,
                                        )
                                    }
                                >
                                    <PiTShirt aria-hidden />
                                    <span>
                                        <strong>{category.name}</strong>
                                        <small>
                                            {count} моделей ·{' '}
                                            {category.is_active
                                                ? 'активна'
                                                : 'скрыта'}
                                        </small>
                                    </span>
                                </button>
                                <button
                                    type="button"
                                    className={styles.iconButton}
                                    aria-label={`Изменить категорию ${category.name}`}
                                    title="Изменить категорию"
                                    onClick={() =>
                                        setCategoryEditor({
                                            id: category.id,
                                            version: category.version,
                                            name: category.name,
                                            is_active: category.is_active,
                                        })
                                    }
                                >
                                    <PiPencilSimple aria-hidden />
                                </button>
                            </article>
                        );
                    })}
            </div>
            <div className={styles.assortmentFilters}>
                <label className={styles.assortmentSearch}>
                    Поиск модели
                    <input
                        value={search}
                        placeholder="Название или код"
                        onChange={(event) => setSearch(event.target.value)}
                    />
                </label>
                <AdminFilters
                    groups={[
                        {
                            key: 'category',
                            label: 'Категория',
                            options: [
                                ['', 'Все категории'],
                                ...(categories.data ?? []).map(
                                    (category) =>
                                        [String(category.id), category.name] as const,
                                ),
                            ],
                        },
                        {
                            key: 'activity',
                            label: 'Видимость',
                            options: [
                                ['', 'Все модели'],
                                ['active', 'Активные'],
                                ['hidden', 'Скрытые'],
                            ],
                        },
                        {
                            key: 'sorting',
                            label: 'Сортировка',
                            options: [
                                ['name:asc', 'Название: А–Я'],
                                ['name:desc', 'Название: Я–А'],
                                ['code:asc', 'По коду'],
                                ['sizes:desc', 'Больше размеров'],
                                ['products:desc', 'Больше товаров'],
                            ],
                        },
                    ]}
                    values={{
                        category: categoryFilter ? String(categoryFilter) : '',
                        activity: activityFilter,
                        sorting,
                    }}
                    defaults={{
                        category: '',
                        activity: '',
                        sorting: 'name:asc',
                    }}
                    onApply={(values) => {
                        setCategoryFilter(Number(values.category) || null);
                        setActivityFilter(values.activity);
                        setSorting(values.sorting);
                    }}
                />
            </div>
            <AssortmentFeedback
                loading={loading || categories.loading}
                error={error || categories.error}
                empty={!loading && models.length === 0}
            />
            {models.length > 0 && (
                <div className={styles.assortmentCards}>
                    {models.map((model) => (
                        <article className={styles.assortmentCard} key={model.id}>
                            <div className={styles.assortmentCardTop}>
                                <div>
                                    <span className={styles.badge}>
                                        {categoryName(model.category_id)}
                                    </span>
                                    <h4>{model.name}</h4>
                                    <small>{model.code}</small>
                                </div>
                                <button
                                    className={styles.iconButton}
                                    onClick={() => openEditor(model)}
                                    aria-label={`Изменить модель ${model.name}`}
                                    title="Изменить"
                                >
                                    <PiPencilSimple aria-hidden />
                                </button>
                            </div>
                            <dl className={styles.compactFacts}>
                                <div>
                                    <dt>Размеров</dt>
                                    <dd>{model.sizes.length}</dd>
                                </div>
                                <div>
                                    <dt>Товаров</dt>
                                    <dd>{model.catalog_product_ids.length}</dd>
                                </div>
                                <div>
                                    <dt>Вес</dt>
                                    <dd>
                                        {model.base_weight_g
                                            ? `${model.base_weight_g} г`
                                            : 'Не задан'}
                                    </dd>
                                </div>
                            </dl>
                            <p className={styles.muted}>
                                {model.published_tech_card
                                    ? `Техкарта: ${model.published_tech_card.name}, версия ${model.published_tech_card.revision_number}`
                                    : 'Опубликованной техкарты нет'}
                            </p>
                        </article>
                    ))}
                </div>
            )}
            {editor && (
                <AssortmentDialog
                    title={editor.id ? 'Изменить модель' : 'Новая модель'}
                    headerActions={
                        <details className={styles.patternStatusMenu}>
                            <summary>
                                <span
                                    className={styles.patternStatusDot}
                                    data-active={editor.is_active}
                                />
                                {editor.is_active ? 'Активна' : 'Скрыта'}
                                <PiCaretDown aria-hidden />
                            </summary>
                            <div role="menu">
                                {([
                                    [true, 'Активна'],
                                    [false, 'Скрыта'],
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
                    description={
                        <span className={styles.modelSetupFlow}>
                            <span>1. Модель</span>
                            <PiArrowRight aria-hidden />
                            <span>2. Размеры</span>
                            <PiArrowRight aria-hidden />
                            <span>3. Диапазоны</span>
                        </span>
                    }
                    onClose={() => setEditor(null)}
                >
                    <form onSubmit={submit}>
                        <fieldset className={styles.formSection}>
                            <legend>Основная информация</legend>
                            <div className={styles.formGrid}>
                                <label>
                                    Категория
                                    <select
                                        required
                                        value={editor.category_id ?? ''}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                category_id:
                                                    Number(event.target.value) || null,
                                            })
                                        }
                                    >
                                        <option value="">Выберите категорию</option>
                                        {(categories.data ?? [])
                                            .filter((category) => category.is_active)
                                            .map((category) => (
                                                <option
                                                    key={category.id}
                                                    value={category.id}
                                                >
                                                    {category.name}
                                                </option>
                                            ))}
                                    </select>
                                </label>
                                <label>
                                    Название
                                    <input
                                        required
                                        value={editor.name}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                name: event.target.value,
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Код
                                    <input
                                        required
                                        value={editor.code}
                                        placeholder="HOODIE_BASE"
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                code: event.target.value.toUpperCase(),
                                            })
                                        }
                                    />
                                </label>
                                <label className={styles.fullField}>
                                    Описание
                                    <textarea
                                        value={editor.description ?? ''}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                description:
                                                    event.target.value || null,
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Базовый размер
                                    <select
                                        required
                                        value={editor.base_size_code ?? ''}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                base_size_code:
                                                    event.target.value || null,
                                            })
                                        }
                                    >
                                        <option value="">Выберите размер</option>
                                        {editor.sizes
                                            .filter((size) => size.code.trim())
                                            .map((size, index) => (
                                                <option
                                                    key={`${size.code}-${index}`}
                                                    value={size.code}
                                                >
                                                    {size.code}
                                                </option>
                                            ))}
                                    </select>
                                    <small>Один из размеров в размерной сетке</small>
                                </label>
                                {(
                                    [
                                        ['base_weight_g', 'Вес, г'],
                                    ] as const
                                ).map(([field, label]) => (
                                    <label key={field}>
                                        {label}
                                        <input
                                            type="number"
                                            min="0.01"
                                            step="0.01"
                                            value={editor[field] ?? ''}
                                            onChange={(event) =>
                                                setEditor({
                                                    ...editor,
                                                    [field]:
                                                        event.target.value || null,
                                                })
                                            }
                                        />
                                    </label>
                                ))}
                                <label>
                                    Имя модели на фото
                                    <input
                                        value={editor.fit_model_name ?? ''}
                                        placeholder="Алексей"
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                fit_model_name:
                                                    event.target.value || null,
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Рост модели на фото, см
                                    <input
                                        type="number"
                                        min="1"
                                        step="1"
                                        value={editor.fit_model_height_cm ?? ''}
                                        placeholder="180"
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                fit_model_height_cm:
                                                    event.target.value || null,
                                            })
                                        }
                                    />
                                </label>
                                <div
                                    className={`${styles.fullField} ${styles.patternFileField}`}
                                >
                                    <span>Таблица размеров для сайта</span>
                                    <label className={styles.patternFilePicker}>
                                        <input
                                            type="file"
                                            accept="image/jpeg,image/png,image/webp"
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
                                                            'public',
                                                        );
                                                    setEditor((current) =>
                                                        current
                                                            ? {
                                                                  ...current,
                                                                  size_chart_media_object_id:
                                                                      uploaded.id,
                                                                  size_chart_url:
                                                                      uploaded.url ??
                                                                      `/production/admin/assortment/media/public/${uploaded.id}`,
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
                                                            : 'Не удалось загрузить изображение';
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
                                            {editor.size_chart_url
                                                ? 'Заменить изображение'
                                                : 'JPEG, PNG или WebP'}
                                        </span>
                                    </label>
                                    <FileUploadStatus value={uploadStatus} />
                                </div>
                                {editor.size_chart_url && (
                                    <figure className={styles.sizeChartPreview}>
                                        {/* eslint-disable-next-line @next/next/no-img-element */}
                                        <img
                                            src={editor.size_chart_url}
                                            alt="Загруженная таблица размеров"
                                        />
                                        <figcaption>
                                            <PiImage aria-hidden />
                                            Изображение добавлено
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    setEditor({
                                                        ...editor,
                                                        size_chart_media_object_id: null,
                                                        size_chart_url: null,
                                                    });
                                                    setUploadStatus(
                                                        idleFileUploadStatus,
                                                    );
                                                }}
                                            >
                                                Удалить
                                            </button>
                                        </figcaption>
                                    </figure>
                                )}
                            </div>
                        </fieldset>
                        <fieldset className={styles.formSection}>
                            <legend>Размерная сетка</legend>
                            <div
                                className={styles.sizeCardList}
                                role="tablist"
                                aria-label="Размеры модели"
                            >
                                {editor.sizes.map((size, index) => (
                                    <button
                                        type="button"
                                        role="tab"
                                        aria-selected={activeSizeIndex === index}
                                        className={styles.sizeCard}
                                        data-selected={activeSizeIndex === index}
                                        key={size.id ?? `new-${index}`}
                                        onClick={() => setActiveSizeIndex(index)}
                                    >
                                        <strong>
                                            {size.code || `Размер ${index + 1}`}
                                        </strong>
                                        <small>{sizeSummary(size)}</small>
                                    </button>
                                ))}
                                <button
                                    type="button"
                                    className={styles.sizeCardAdd}
                                    onClick={() => {
                                        const nextIndex = editor.sizes.length;
                                        setEditor({
                                            ...editor,
                                            sizes: [
                                                ...editor.sizes,
                                                emptySize(nextIndex),
                                            ],
                                        });
                                        setActiveSizeIndex(nextIndex);
                                    }}
                                >
                                    <PiPlus aria-hidden />
                                    <span>Добавить размер</span>
                                </button>
                            </div>
                            {activeSize && (
                                <article className={styles.sizeDetailCard}>
                                    <div className={styles.sizeDetailHeading}>
                                        <div>
                                            <h4>
                                                {activeSize.code ||
                                                    `Размер ${activeSizeIndex + 1}`}
                                            </h4>
                                            <small>
                                                Укажите границы, доступные покупателю
                                            </small>
                                        </div>
                                        <button
                                            type="button"
                                            className={styles.iconButton}
                                            disabled={editor.sizes.length === 1}
                                            onClick={() => {
                                                const sizes = editor.sizes.filter(
                                                    (_, index) =>
                                                        index !== activeSizeIndex,
                                                );
                                                const removedCode =
                                                    editor.sizes[activeSizeIndex]?.code;
                                                setEditor({
                                                    ...editor,
                                                    sizes,
                                                    base_size_code:
                                                        editor.base_size_code ===
                                                        removedCode
                                                            ? sizes[0]?.code || null
                                                            : editor.base_size_code,
                                                });
                                                setActiveSizeIndex((current) =>
                                                    Math.max(
                                                        0,
                                                        Math.min(
                                                            current,
                                                            sizes.length - 1,
                                                        ),
                                                    ),
                                                );
                                            }}
                                            aria-label={`Удалить размер ${activeSize.code || activeSizeIndex + 1}`}
                                        >
                                            <PiTrash aria-hidden />
                                        </button>
                                    </div>
                                    <div className={styles.sizePrimaryFields}>
                                        <label>
                                            Код размера
                                            <input
                                                required
                                                value={activeSize.code}
                                                placeholder="M"
                                                onChange={(event) => {
                                                    const nextCode =
                                                        event.target.value.toUpperCase();
                                                    setEditor((current) => {
                                                        if (!current) return current;
                                                        const sizes = [
                                                            ...current.sizes,
                                                        ];
                                                        const previousCode =
                                                            sizes[activeSizeIndex].code;
                                                        sizes[activeSizeIndex] = {
                                                            ...sizes[activeSizeIndex],
                                                            code: nextCode,
                                                        };
                                                        return {
                                                            ...current,
                                                            sizes,
                                                            base_size_code:
                                                                !current.base_size_code ||
                                                                current.base_size_code ===
                                                                    previousCode
                                                                    ? nextCode || null
                                                                    : current.base_size_code,
                                                        };
                                                    });
                                                }}
                                            />
                                        </label>
                                        <label>
                                            Базовая цена
                                            <input
                                                type="number"
                                                min="0"
                                                step="0.01"
                                                value={activeSize.base_price}
                                                onChange={(event) =>
                                                    updateSize(
                                                        activeSizeIndex,
                                                        'base_price',
                                                        event.target.value,
                                                    )
                                                }
                                            />
                                        </label>
                                        <label>
                                            Базовая ширина, см
                                            <input
                                                required
                                                type="number"
                                                min="0.1"
                                                step="0.1"
                                                inputMode="decimal"
                                                value={activeSize.base_width_cm ?? ''}
                                                placeholder="60"
                                                onChange={(event) =>
                                                    updateSize(
                                                        activeSizeIndex,
                                                        'base_width_cm',
                                                        event.target.value,
                                                    )
                                                }
                                            />
                                        </label>
                                        <label>
                                            Базовая длина, см
                                            <input
                                                required
                                                type="number"
                                                min="0.1"
                                                step="0.1"
                                                inputMode="decimal"
                                                value={activeSize.base_length_cm ?? ''}
                                                placeholder="72"
                                                onChange={(event) =>
                                                    updateSize(
                                                        activeSizeIndex,
                                                        'base_length_cm',
                                                        event.target.value,
                                                    )
                                                }
                                            />
                                        </label>
                                    </div>
                                    <div className={styles.sizeRangeGrid}>
                                        <SizeRangeEditor
                                            label="Ширина изделия"
                                            size={activeSize}
                                            minimum="min_width_cm"
                                            maximum="max_width_cm"
                                            onChange={(field, value) =>
                                                updateSize(
                                                    activeSizeIndex,
                                                    field,
                                                    value,
                                                )
                                            }
                                        />
                                        <section className={styles.sizeRangeCard}>
                                            <div className={styles.sizeRangeHeading}>
                                                <PiRuler aria-hidden />
                                                <strong>Длина по росту</strong>
                                            </div>
                                            <div className={styles.lengthHeightRows}>
                                                {([
                                                    [
                                                        'min_length_cm',
                                                        'min_height_cm',
                                                        'Минимум',
                                                    ],
                                                    [
                                                        'max_length_cm',
                                                        'max_height_cm',
                                                        'Максимум',
                                                    ],
                                                ] as const).map(
                                                    ([lengthField, heightField, label]) => (
                                                        <div key={lengthField}>
                                                            <small>{label}</small>
                                                            <label>
                                                                Длина
                                                                <span>
                                                                    <input
                                                                        type="number"
                                                                        min="0"
                                                                        step="2"
                                                                        value={
                                                                            activeSize[
                                                                                lengthField
                                                                            ] ?? ''
                                                                        }
                                                                        onChange={(event) =>
                                                                            updateSize(
                                                                                activeSizeIndex,
                                                                                lengthField,
                                                                                event.target.value,
                                                                            )
                                                                        }
                                                                    />
                                                                    см
                                                                </span>
                                                            </label>
                                                            <PiArrowRight aria-hidden />
                                                            <label>
                                                                Рост человека
                                                                <span>
                                                                    <input
                                                                        type="number"
                                                                        min="0"
                                                                        step="1"
                                                                        value={
                                                                            activeSize[
                                                                                heightField
                                                                            ] ?? ''
                                                                        }
                                                                        onChange={(event) =>
                                                                            updateSize(
                                                                                activeSizeIndex,
                                                                                heightField,
                                                                                event.target.value,
                                                                            )
                                                                        }
                                                                    />
                                                                    см
                                                                </span>
                                                            </label>
                                                        </div>
                                                    ),
                                                )}
                                            </div>
                                        </section>
                                        <section className={styles.sizeRangeCard}>
                                            <div className={styles.sizeRangeHeading}>
                                                <PiRuler aria-hidden />
                                                <strong>Варианты рукава</strong>
                                            </div>
                                            <div className={styles.squareChoiceGrid}>
                                                {([
                                                    [
                                                        'allow_standard_sleeve',
                                                        'Стандартный',
                                                        'По лекалу',
                                                    ],
                                                    [
                                                        'allow_height_sleeve',
                                                        'Под рост',
                                                        'По росту человека',
                                                    ],
                                                ] as const).map(
                                                    ([field, label, hint]) => {
                                                        const selected = activeSize[field];
                                                        const otherSelected =
                                                            field ===
                                                            'allow_standard_sleeve'
                                                                ? activeSize.allow_height_sleeve
                                                                : activeSize.allow_standard_sleeve;
                                                        return (
                                                            <button
                                                                type="button"
                                                                key={field}
                                                                data-selected={selected}
                                                                aria-pressed={selected}
                                                                disabled={
                                                                    selected && !otherSelected
                                                                }
                                                                onClick={() =>
                                                                    setEditor((current) => {
                                                                        if (!current)
                                                                            return current;
                                                                        const sizes = [
                                                                            ...current.sizes,
                                                                        ];
                                                                        sizes[activeSizeIndex] = {
                                                                            ...sizes[
                                                                                activeSizeIndex
                                                                            ],
                                                                            [field]: !selected,
                                                                        };
                                                                        return {
                                                                            ...current,
                                                                            sizes,
                                                                        };
                                                                    })
                                                                }
                                                            >
                                                                <PiCheck aria-hidden />
                                                                <strong>{label}</strong>
                                                                <small>{hint}</small>
                                                            </button>
                                                        );
                                                    },
                                                )}
                                            </div>
                                        </section>
                                    </div>
                                </article>
                            )}
                        </fieldset>
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
                                {saving ? 'Сохраняем…' : 'Сохранить модель'}
                            </button>
                        </div>
                    </form>
                </AssortmentDialog>
            )}
            {categoryEditor && (
                <AssortmentDialog
                    title={
                        categoryEditor.id
                            ? 'Изменить категорию'
                            : 'Новая категория моделей'
                    }
                    headerActions={
                        <details className={styles.patternStatusMenu}>
                            <summary>
                                <span
                                    className={styles.patternStatusDot}
                                    data-active={categoryEditor.is_active}
                                />
                                {categoryEditor.is_active ? 'Активна' : 'Скрыта'}
                                <PiCaretDown aria-hidden />
                            </summary>
                            <div role="menu">
                                {([
                                    [true, 'Активна'],
                                    [false, 'Скрыта'],
                                ] as const).map(([active, label]) => (
                                    <button
                                        type="button"
                                        role="menuitemradio"
                                        aria-checked={
                                            categoryEditor.is_active === active
                                        }
                                        key={String(active)}
                                        onClick={(event) => {
                                            setCategoryEditor({
                                                ...categoryEditor,
                                                is_active: active,
                                            });
                                            event.currentTarget
                                                .closest('details')
                                                ?.removeAttribute('open');
                                        }}
                                    >
                                        <span>{label}</span>
                                        {categoryEditor.is_active === active && (
                                            <PiCheck aria-hidden />
                                        )}
                                    </button>
                                ))}
                            </div>
                        </details>
                    }
                    onClose={() => setCategoryEditor(null)}
                >
                    <form onSubmit={submitCategory}>
                        <div className={styles.formGrid}>
                            <label>
                                Название
                                <input
                                    required
                                    maxLength={120}
                                    value={categoryEditor.name}
                                    placeholder="Худи"
                                    onChange={(event) =>
                                        setCategoryEditor({
                                            ...categoryEditor,
                                            name: event.target.value,
                                        })
                                    }
                                />
                            </label>
                        </div>
                        {formError && (
                            <p className={styles.error} role="alert">
                                {formError}
                            </p>
                        )}
                        <div className={styles.editorActions}>
                            <button
                                type="button"
                                onClick={() => setCategoryEditor(null)}
                            >
                                Отмена
                            </button>
                            <button
                                className={styles.primaryButton}
                                disabled={saving}
                            >
                                {saving ? 'Сохраняем…' : 'Сохранить категорию'}
                            </button>
                        </div>
                    </form>
                </AssortmentDialog>
            )}
        </section>
    );
}
