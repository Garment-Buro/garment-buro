'use client';

import { useMemo, useState, type FormEvent } from 'react';
import { PiPencilSimple, PiPlus, PiTrash } from 'react-icons/pi';
import { useAssortmentResource } from '@/hooks/production/useAssortmentResource';
import {
    saveAssortment,
    uploadAssortmentMedia,
} from '@/lib/api/productionAssortment';
import type {
    GarmentModel,
    GarmentSize,
    ReferencePage,
} from '@/lib/production/assortmentTypes';
import { AssortmentDialog, AssortmentFeedback } from './AssortmentDialog';
import styles from '../ProductionAdmin.module.css';

const emptySize = (sortOrder: number): GarmentSize => ({
    code: '',
    sort_order: sortOrder,
    base_price: '0',
    min_height_cm: null,
    max_height_cm: null,
    min_length_cm: null,
    max_length_cm: null,
    min_width_cm: null,
    max_width_cm: null,
    min_sleeve_length_cm: null,
    max_sleeve_length_cm: null,
    extra_width_price_per_cm: null,
});

type ModelForm = Omit<
    GarmentModel,
    'id' | 'version' | 'catalog_product_ids' | 'published_tech_card'
> & { id?: number; version?: number };

const emptyModel = (): ModelForm => ({
    code: '',
    name: '',
    description: null,
    base_height_cm: null,
    base_length_cm: null,
    base_width_cm: null,
    base_weight_g: null,
    size_chart_media_object_id: null,
    is_active: true,
    sizes: [emptySize(0)],
});

const optionalNumber = (value: string | null | undefined) =>
    value == null || value === '' ? null : Number(value);

export function AdminModels() {
    const { data, loading, error, reload } =
        useAssortmentResource<ReferencePage<GarmentModel>>('models');
    const [search, setSearch] = useState('');
    const [editor, setEditor] = useState<ModelForm | null>(null);
    const [saving, setSaving] = useState(false);
    const [formError, setFormError] = useState('');
    const [uploading, setUploading] = useState(false);
    const models = useMemo(() => {
        const query = search.trim().toLocaleLowerCase('ru');
        if (!query) return data?.items ?? [];
        return (data?.items ?? []).filter((model) =>
            `${model.name} ${model.code}`.toLocaleLowerCase('ru').includes(query),
        );
    }, [data, search]);

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
            code: editor.code,
            name: editor.name,
            description: editor.description,
            base_height_cm: optionalNumber(editor.base_height_cm),
            base_length_cm: optionalNumber(editor.base_length_cm),
            base_width_cm: optionalNumber(editor.base_width_cm),
            base_weight_g: optionalNumber(editor.base_weight_g),
            size_chart_media_object_id: editor.size_chart_media_object_id,
            is_active: editor.is_active,
            sizes: editor.sizes.map((size, index) => ({
                code: size.code,
                sort_order: index,
                base_price: Number(size.base_price || 0),
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

    return (
        <section aria-busy={loading}>
            <div className={styles.assortmentHeading}>
                <div>
                    <h3>Модели изделий</h3>
                    <p className={styles.muted}>
                        Размеры, диапазоны мерок, вес и таблица размеров для сайта.
                    </p>
                </div>
                <button onClick={() => setEditor(emptyModel())}>
                    <PiPlus aria-hidden /> Добавить модель
                </button>
            </div>
            <label className={styles.assortmentSearch}>
                Поиск модели
                <input
                    value={search}
                    placeholder="Название или код"
                    onChange={(event) => setSearch(event.target.value)}
                />
            </label>
            <AssortmentFeedback
                loading={loading}
                error={error}
                empty={!loading && models.length === 0}
            />
            {models.length > 0 && (
                <div className={styles.assortmentCards}>
                    {models.map((model) => (
                        <article className={styles.assortmentCard} key={model.id}>
                            <div className={styles.assortmentCardTop}>
                                <div>
                                    <span className={styles.badge}>{model.code}</span>
                                    <h4>{model.name}</h4>
                                </div>
                                <button
                                    className={styles.iconButton}
                                    onClick={() =>
                                        setEditor({
                                            ...model,
                                            sizes: model.sizes.map((size) => ({
                                                ...size,
                                            })),
                                        })
                                    }
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
                    description="Сначала задайте общие параметры, затем добавьте размеры и допустимые диапазоны."
                    onClose={() => setEditor(null)}
                >
                    <form onSubmit={submit}>
                        <fieldset className={styles.formSection}>
                            <legend>Основная информация</legend>
                            <div className={styles.formGrid}>
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
                                {(
                                    [
                                        ['base_weight_g', 'Вес, г'],
                                        ['base_height_cm', 'Базовый рост, см'],
                                        ['base_width_cm', 'Базовая ширина, см'],
                                        ['base_length_cm', 'Базовая длина, см'],
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
                                <label className={styles.fullField}>
                                    Таблица размеров для сайта
                                    <input
                                        type="file"
                                        accept="image/jpeg,image/png,image/webp"
                                        disabled={uploading}
                                        onChange={async (event) => {
                                            const file = event.target.files?.[0];
                                            if (!file) return;
                                            setUploading(true);
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
                                                          }
                                                        : current,
                                                );
                                            } catch (reason) {
                                                setFormError(
                                                    reason instanceof Error
                                                        ? reason.message
                                                        : 'Не удалось загрузить изображение',
                                                );
                                            } finally {
                                                setUploading(false);
                                            }
                                        }}
                                    />
                                    <small>
                                        {editor.size_chart_media_object_id
                                            ? `Медиа №${editor.size_chart_media_object_id}`
                                            : 'JPEG, PNG или WebP'}
                                    </small>
                                </label>
                                <label className={styles.checkField}>
                                    <input
                                        type="checkbox"
                                        checked={editor.is_active}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                is_active: event.target.checked,
                                            })
                                        }
                                    />
                                    Модель активна
                                </label>
                            </div>
                        </fieldset>
                        <fieldset className={styles.formSection}>
                            <legend>Размерная сетка</legend>
                            <div className={styles.sizeList}>
                                {editor.sizes.map((size, index) => (
                                    <article className={styles.sizeEditor} key={index}>
                                        <div className={styles.assortmentCardTop}>
                                            <h4>Размер {index + 1}</h4>
                                            <button
                                                type="button"
                                                className={styles.iconButton}
                                                disabled={editor.sizes.length === 1}
                                                onClick={() =>
                                                    setEditor({
                                                        ...editor,
                                                        sizes: editor.sizes.filter(
                                                            (_, itemIndex) =>
                                                                itemIndex !== index,
                                                        ),
                                                    })
                                                }
                                                aria-label={`Удалить размер ${index + 1}`}
                                            >
                                                <PiTrash aria-hidden />
                                            </button>
                                        </div>
                                        <div className={styles.measureGrid}>
                                            <label>
                                                Код размера
                                                <input
                                                    required
                                                    value={size.code}
                                                    placeholder="M"
                                                    onChange={(event) =>
                                                        updateSize(
                                                            index,
                                                            'code',
                                                            event.target.value.toUpperCase(),
                                                        )
                                                    }
                                                />
                                            </label>
                                            <label>
                                                Базовая цена
                                                <input
                                                    type="number"
                                                    min="0"
                                                    step="0.01"
                                                    value={size.base_price}
                                                    onChange={(event) =>
                                                        updateSize(
                                                            index,
                                                            'base_price',
                                                            event.target.value,
                                                        )
                                                    }
                                                />
                                            </label>
                                            {(
                                                [
                                                    ['min_width_cm', 'Ширина от'],
                                                    ['max_width_cm', 'Ширина до'],
                                                    ['min_length_cm', 'Длина от'],
                                                    ['max_length_cm', 'Длина до'],
                                                    ['min_height_cm', 'Рост от'],
                                                    ['max_height_cm', 'Рост до'],
                                                    [
                                                        'min_sleeve_length_cm',
                                                        'Рукав от',
                                                    ],
                                                    [
                                                        'max_sleeve_length_cm',
                                                        'Рукав до',
                                                    ],
                                                ] as const
                                            ).map(([field, label]) => (
                                                <label key={field}>
                                                    {label}, см
                                                    <input
                                                        type="number"
                                                        min="0.01"
                                                        step="0.01"
                                                        value={size[field] ?? ''}
                                                        onChange={(event) =>
                                                            updateSize(
                                                                index,
                                                                field,
                                                                event.target.value,
                                                            )
                                                        }
                                                    />
                                                </label>
                                            ))}
                                        </div>
                                    </article>
                                ))}
                            </div>
                            <button
                                type="button"
                                onClick={() =>
                                    setEditor({
                                        ...editor,
                                        sizes: [
                                            ...editor.sizes,
                                            emptySize(editor.sizes.length),
                                        ],
                                    })
                                }
                            >
                                <PiPlus aria-hidden /> Добавить размер
                            </button>
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
        </section>
    );
}
