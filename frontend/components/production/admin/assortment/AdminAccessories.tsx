'use client';

import { useRef, useState, type FormEvent } from 'react';
import { PiLink, PiPencilSimple, PiPlus, PiUploadSimple } from 'react-icons/pi';
import {
    useAccessoryDirectory,
    useAccessoryCategories,
    useAccessoryRequirements,
} from '@/hooks/production/useReferenceDirectory';
import { ReferencePicker } from './ReferencePicker';
import {
    saveAssortment,
    uploadAssortmentMedia,
} from '@/lib/api/productionAssortment';
import { compactDecimal } from '@/lib/production/numbers';
import type {
    Accessory,
    AccessoryCategory,
    AccessoryRequirement,
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

type CategoryForm = Partial<AccessoryCategory> & {
    code: string;
    name: string;
    description: string | null;
    is_active: boolean;
};
type AccessoryForm = Partial<Accessory> & {
    category_id: number;
    code: string;
    name: string;
    unit_cost: string;
    stock_quantity: number;
    minimum_stock_quantity: number;
    photo_media_object_id: number | null;
    is_active: boolean;
};
type RequirementForm = Partial<AccessoryRequirement> & {
    garment_model_id: number;
    accessory_id: number;
    quantity_per_unit: string;
    is_optional: boolean;
    notes: string | null;
};

export function AdminAccessories() {
    const [search, setSearch] = useState('');
    const [categoryFilter, setCategoryFilter] = useState('');
    const [activityFilter, setActivityFilter] = useState('');
    const [stockFilter, setStockFilter] = useState('');
    const [sorting, setSorting] = useState('name:asc');
    const [categoryEditor, setCategoryEditor] = useState<CategoryForm | null>(
        null,
    );
    const [editor, setEditor] = useState<AccessoryForm | null>(null);
    const [requirementEditor, setRequirementEditor] =
        useState<RequirementForm | null>(null);
    const [saving, setSaving] = useState(false);
    const writeLocked = useRef(false);
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] =
        useState<FileUploadStatusValue>(idleFileUploadStatus);
    const [formError, setFormError] = useState('');
    const [categorySearch, setCategorySearch] = useState('');
    const [requirementSearch, setRequirementSearch] = useState('');
    const [categorySelection, setCategorySelection] = useState<{
        id: string;
        name: string;
    } | null>(null);
    const accessories = useAccessoryDirectory({
        query: search,
        category_id: Number(categoryFilter) || null,
        active: activityFilter ? activityFilter === 'active' : undefined,
        stock: stockFilter || 'all',
        sort: sorting,
        limit: 24,
    });
    const categories = useAccessoryCategories({
        query: categorySearch,
        limit: 24,
    });
    const requirements = useAccessoryRequirements({
        query: requirementSearch,
        limit: 24,
    });
    const visibleAccessories = accessories.items;

    const runSave = async (
        path: string,
        method: 'POST' | 'PUT',
        payload: unknown,
        done: () => void,
    ) => {
        if (writeLocked.current) return;
        writeLocked.current = true;
        setSaving(true);
        setFormError('');
        try {
            await saveAssortment(path, method, payload);
            done();
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось сохранить запись',
            );
        } finally {
            writeLocked.current = false;
            setSaving(false);
        }
    };
    const submitCategory = (event: FormEvent) => {
        event.preventDefault();
        if (!categoryEditor) return;
        void runSave(
            categoryEditor.id
                ? `accessory-categories/${categoryEditor.id}`
                : 'accessory-categories',
            categoryEditor.id ? 'PUT' : 'POST',
            {
                code: categoryEditor.code,
                name: categoryEditor.name,
                description: categoryEditor.description,
                is_active: categoryEditor.is_active,
                ...(categoryEditor.id
                    ? { expected_version: categoryEditor.version }
                    : {}),
            },
            () => {
                setCategorySelection((current) =>
                    current?.id === String(categoryEditor.id)
                        ? { ...current, name: categoryEditor.name.trim() }
                        : current,
                );
                setCategoryEditor(null);
                categories.retry();
            },
        );
    };
    const submitAccessory = (event: FormEvent) => {
        event.preventDefault();
        if (!editor) return;
        void runSave(
            editor.id ? `accessories/${editor.id}` : 'accessories',
            editor.id ? 'PUT' : 'POST',
            {
                category_id: editor.category_id,
                code: editor.code,
                name: editor.name,
                unit_cost: Number(editor.unit_cost || 0),
                currency: 'RUB',
                stock_quantity: Number(editor.stock_quantity),
                minimum_stock_quantity: Number(editor.minimum_stock_quantity),
                photo_media_object_id: editor.photo_media_object_id,
                is_active: editor.is_active,
                ...(editor.id ? { expected_version: editor.version } : {}),
            },
            () => {
                setEditor(null);
                accessories.retry();
            },
        );
    };
    const submitRequirement = (event: FormEvent) => {
        event.preventDefault();
        if (!requirementEditor) return;
        void runSave(
            requirementEditor.id
                ? `accessory-requirements/${requirementEditor.id}`
                : 'accessory-requirements',
            requirementEditor.id ? 'PUT' : 'POST',
            {
                garment_model_id: requirementEditor.garment_model_id,
                accessory_id: requirementEditor.accessory_id,
                quantity_per_unit: Number(requirementEditor.quantity_per_unit),
                is_optional: requirementEditor.is_optional,
                notes: requirementEditor.notes,
                ...(requirementEditor.id
                    ? { expected_version: requirementEditor.version }
                    : {}),
            },
            () => {
                setRequirementEditor(null);
                requirements.retry();
                accessories.retry();
            },
        );
    };

    return (
        <section aria-busy={accessories.loading}>
            <fieldset
                className={styles.adminFields}
                disabled={saving || uploading}
            >
                <div className={styles.assortmentHeading}>
                    <div>
                        <h3>Фурнитура</h3>
                        <p className={styles.muted}>
                            Категории, остатки и применимость фурнитуры к
                            моделям.
                        </p>
                    </div>
                    <div className={styles.headingActions}>
                        <button
                            onClick={() =>
                                setCategoryEditor({
                                    code: '',
                                    name: '',
                                    description: null,
                                    is_active: true,
                                })
                            }
                        >
                            <PiPlus aria-hidden /> Категория
                        </button>
                        <button
                            onClick={() => {
                                setUploadStatus(idleFileUploadStatus);
                                setEditor({
                                    category_id: 0,
                                    code: '',
                                    name: '',
                                    unit_cost: '0',
                                    stock_quantity: 0,
                                    minimum_stock_quantity: 0,
                                    photo_media_object_id: null,
                                    is_active: true,
                                });
                            }}
                        >
                            <PiPlus aria-hidden /> Добавить фурнитуру
                        </button>
                    </div>
                </div>
                <label>
                    Найти категорию фурнитуры
                    <input
                        type="search"
                        value={categorySearch}
                        onChange={(event) =>
                            setCategorySearch(event.target.value)
                        }
                    />
                </label>
                {categories.message && (
                    <p role="alert">
                        {categories.message}
                        <button
                            type="button"
                            onClick={() => void categories.retry()}
                        >
                            Обновить категории фурнитуры
                        </button>
                    </p>
                )}
                <div
                    className={styles.chipList}
                    aria-label="Категории фурнитуры"
                >
                    {categories.items.map((category) => (
                        <button
                            key={category.id}
                            onClick={() => setCategoryEditor({ ...category })}
                        >
                            {category.name}
                        </button>
                    ))}
                </div>
                {categories.hasMore && (
                    <button
                        type="button"
                        disabled={categories.loadingMore}
                        onClick={() => void categories.loadMore()}
                    >
                        Ещё категории
                    </button>
                )}
                <div className={styles.assortmentFilters}>
                    <label className={styles.assortmentSearch}>
                        Поиск фурнитуры
                        <input
                            type="search"
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
                                    ...(categorySelection &&
                                    !categories.items.some(
                                        (row) =>
                                            String(row.id) ===
                                            categorySelection.id,
                                    )
                                        ? [
                                              [
                                                  categorySelection.id,
                                                  categorySelection.name,
                                              ] as const,
                                          ]
                                        : []),
                                    ...categories.items.map(
                                        (category) =>
                                            [
                                                String(category.id),
                                                category.name,
                                            ] as const,
                                    ),
                                ],
                            },
                            {
                                key: 'activity',
                                label: 'Видимость',
                                options: [
                                    ['', 'Все позиции'],
                                    ['active', 'Активные'],
                                    ['hidden', 'Скрытые'],
                                ],
                            },
                            {
                                key: 'stock',
                                label: 'Остаток',
                                options: [
                                    ['', 'Любой остаток'],
                                    ['available', 'Выше минимума'],
                                    ['low', 'Заканчивается'],
                                ],
                            },
                            {
                                key: 'sorting',
                                label: 'Сортировка',
                                options: [
                                    ['name:asc', 'Название: А–Я'],
                                    ['code:asc', 'По коду'],
                                    ['stock:asc', 'Сначала заканчивающиеся'],
                                    ['stock:desc', 'Сначала большие остатки'],
                                    ['price:asc', 'Сначала дешевле'],
                                    ['price:desc', 'Сначала дороже'],
                                ],
                            },
                        ]}
                        values={{
                            category: categoryFilter,
                            activity: activityFilter,
                            stock: stockFilter,
                            sorting,
                        }}
                        defaults={{
                            category: '',
                            activity: '',
                            stock: '',
                            sorting: 'name:asc',
                        }}
                        onApply={(values) => {
                            setCategoryFilter(values.category);
                            setCategorySelection(
                                values.category
                                    ? {
                                          id: values.category,
                                          name:
                                              categories.items.find(
                                                  (row) =>
                                                      String(row.id) ===
                                                      values.category,
                                              )?.name ??
                                              categorySelection?.name ??
                                              `№${values.category}`,
                                      }
                                    : null,
                            );
                            setActivityFilter(values.activity);
                            setStockFilter(values.stock);
                            setSorting(values.sorting);
                        }}
                    />
                </div>
                <AssortmentFeedback
                    loading={accessories.loading}
                    error={accessories.message}
                    empty={
                        !accessories.loading && visibleAccessories.length === 0
                    }
                />
                <div className={styles.assortmentCards}>
                    {visibleAccessories.map((item) => (
                        <article
                            className={styles.assortmentCard}
                            key={item.id}
                        >
                            <div className={styles.assortmentCardTop}>
                                <div>
                                    <span className={styles.badge}>
                                        {item.category_name}
                                    </span>
                                    <h4>{item.name}</h4>
                                    <small>{item.code}</small>
                                </div>
                                <button
                                    className={styles.iconButton}
                                    onClick={() => {
                                        setUploadStatus(
                                            item.photo_media_object_id
                                                ? {
                                                      state: 'success',
                                                      message:
                                                          'Фото уже загружено',
                                                  }
                                                : idleFileUploadStatus,
                                        );
                                        setEditor({
                                            ...item,
                                            unit_cost: compactDecimal(
                                                item.unit_cost,
                                            ),
                                        });
                                    }}
                                    aria-label={`Изменить ${item.name}`}
                                >
                                    <PiPencilSimple aria-hidden />
                                </button>
                            </div>
                            <dl className={styles.compactFacts}>
                                <div>
                                    <dt>Остаток</dt>
                                    <dd>{item.stock_quantity}</dd>
                                </div>
                                <div>
                                    <dt>Минимум</dt>
                                    <dd>{item.minimum_stock_quantity}</dd>
                                </div>
                                <div>
                                    <dt>Цена</dt>
                                    <dd>{compactDecimal(item.unit_cost)} ₽</dd>
                                </div>
                            </dl>
                            <p className={styles.muted}>
                                {item.model_count
                                    ? `Подходит для ${item.model_count} моделей`
                                    : 'Модели пока не назначены'}
                            </p>
                            <button
                                onClick={() =>
                                    setRequirementEditor({
                                        garment_model_id: 0,
                                        accessory_id: item.id,
                                        quantity_per_unit: '1',
                                        is_optional: false,
                                        notes: null,
                                    })
                                }
                            >
                                <PiLink aria-hidden /> Назначить модели
                            </button>
                        </article>
                    ))}
                </div>
                {accessories.message && (
                    <button
                        type="button"
                        onClick={() => void accessories.retry()}
                    >
                        Обновить фурнитуру
                    </button>
                )}
                {accessories.hasMore && (
                    <button
                        type="button"
                        disabled={accessories.loadingMore}
                        onClick={() => void accessories.loadMore()}
                    >
                        Ещё фурнитура
                    </button>
                )}
                <section className={styles.relatedSection}>
                    <h4>Применимость и расход</h4>
                    <label>
                        Поиск расхода фурнитуры
                        <input
                            type="search"
                            value={requirementSearch}
                            onChange={(event) =>
                                setRequirementSearch(event.target.value)
                            }
                        />
                    </label>
                    <AssortmentFeedback
                        loading={requirements.loading}
                        error={requirements.message}
                        empty={
                            !requirements.loading && !requirements.items.length
                        }
                    />
                    {requirements.message && (
                        <button
                            type="button"
                            onClick={() => void requirements.retry()}
                        >
                            Обновить расход фурнитуры
                        </button>
                    )}
                    <div className={styles.relationshipList}>
                        {requirements.items.map((item) => (
                            <button
                                key={item.id}
                                className={styles.relationshipCard}
                                onClick={() =>
                                    setRequirementEditor({
                                        ...item,
                                        quantity_per_unit: compactDecimal(
                                            item.quantity_per_unit,
                                        ),
                                    })
                                }
                            >
                                <span>
                                    <strong>{item.accessory_name}</strong>
                                    <small>{item.garment_model_name}</small>
                                </span>
                                <span>
                                    {compactDecimal(item.quantity_per_unit)} шт.
                                </span>
                            </button>
                        ))}
                    </div>
                    {requirements.hasMore && (
                        <button
                            type="button"
                            disabled={requirements.loadingMore}
                            onClick={() => void requirements.loadMore()}
                        >
                            Ещё расход фурнитуры
                        </button>
                    )}
                </section>
                {categoryEditor && (
                    <AssortmentDialog
                        title={
                            categoryEditor.id
                                ? 'Изменить категорию'
                                : 'Новая категория'
                        }
                        onClose={() => setCategoryEditor(null)}
                    >
                        <form onSubmit={submitCategory}>
                            <div className={styles.formGrid}>
                                <label>
                                    Название
                                    <input
                                        required
                                        value={categoryEditor.name}
                                        onChange={(event) =>
                                            setCategoryEditor({
                                                ...categoryEditor,
                                                name: event.target.value,
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Код
                                    <input
                                        required
                                        value={categoryEditor.code}
                                        onChange={(event) =>
                                            setCategoryEditor({
                                                ...categoryEditor,
                                                code: event.target.value.toUpperCase(),
                                            })
                                        }
                                    />
                                </label>
                                <label className={styles.fullField}>
                                    Описание
                                    <textarea
                                        value={categoryEditor.description ?? ''}
                                        onChange={(event) =>
                                            setCategoryEditor({
                                                ...categoryEditor,
                                                description:
                                                    event.target.value || null,
                                            })
                                        }
                                    />
                                </label>
                                <label className={styles.checkField}>
                                    <input
                                        type="checkbox"
                                        checked={categoryEditor.is_active}
                                        onChange={(event) =>
                                            setCategoryEditor({
                                                ...categoryEditor,
                                                is_active: event.target.checked,
                                            })
                                        }
                                    />
                                    Категория активна
                                </label>
                            </div>
                            {formError && (
                                <p className={styles.error}>{formError}</p>
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
                                    Сохранить
                                </button>
                            </div>
                        </form>
                    </AssortmentDialog>
                )}
                {editor && (
                    <AssortmentDialog
                        title={
                            editor.id ? 'Изменить фурнитуру' : 'Новая фурнитура'
                        }
                        onClose={() => setEditor(null)}
                    >
                        <form onSubmit={submitAccessory}>
                            <div className={styles.formGrid}>
                                <ReferencePicker
                                    kind="accessory-categories"
                                    value={editor.category_id}
                                    onChange={(category_id) =>
                                        setEditor({ ...editor, category_id })
                                    }
                                />
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
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                code: event.target.value.toUpperCase(),
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Цена за единицу
                                    <input
                                        type="number"
                                        min="0"
                                        step="0.01"
                                        value={editor.unit_cost}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                unit_cost: event.target.value,
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Остаток
                                    <input
                                        type="number"
                                        min="0"
                                        value={editor.stock_quantity}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                stock_quantity: Number(
                                                    event.target.value,
                                                ),
                                            })
                                        }
                                    />
                                </label>
                                <label>
                                    Минимальный остаток
                                    <input
                                        type="number"
                                        min="0"
                                        value={editor.minimum_stock_quantity}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                minimum_stock_quantity: Number(
                                                    event.target.value,
                                                ),
                                            })
                                        }
                                    />
                                </label>
                                <div
                                    className={`${styles.fullField} ${styles.patternFileField}`}
                                >
                                    <span>Фото</span>
                                    <label className={styles.patternFilePicker}>
                                        <input
                                            type="file"
                                            accept="image/jpeg,image/png,image/webp"
                                            disabled={uploading}
                                            onChange={async (event) => {
                                                const file =
                                                    event.target.files?.[0];
                                                if (!file) return;
                                                setUploading(true);
                                                setFormError('');
                                                setUploadStatus({
                                                    state: 'uploading',
                                                    fileName: file.name,
                                                });
                                                try {
                                                    const media =
                                                        await uploadAssortmentMedia(
                                                            file,
                                                            'public',
                                                        );
                                                    setEditor((current) =>
                                                        current
                                                            ? {
                                                                  ...current,
                                                                  photo_media_object_id:
                                                                      media.id,
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
                                                            : 'Не удалось загрузить фото';
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
                                        <span>JPEG, PNG или WebP</span>
                                    </label>
                                    <FileUploadStatus value={uploadStatus} />
                                </div>
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
                                    Доступна
                                </label>
                            </div>
                            {formError && (
                                <p className={styles.error}>{formError}</p>
                            )}
                            <div className={styles.editorActions}>
                                <button
                                    type="button"
                                    onClick={() => setEditor(null)}
                                >
                                    Отмена
                                </button>
                                <button
                                    className={styles.primaryButton}
                                    disabled={saving || uploading}
                                >
                                    Сохранить
                                </button>
                            </div>
                        </form>
                    </AssortmentDialog>
                )}
                {requirementEditor && (
                    <AssortmentDialog
                        title="Применимость фурнитуры"
                        onClose={() => setRequirementEditor(null)}
                    >
                        <form onSubmit={submitRequirement}>
                            <div className={styles.formGrid}>
                                <ReferencePicker
                                    kind="models"
                                    value={requirementEditor.garment_model_id}
                                    onChange={(garment_model_id) =>
                                        setRequirementEditor({
                                            ...requirementEditor,
                                            garment_model_id,
                                        })
                                    }
                                />
                                <ReferencePicker
                                    kind="accessories"
                                    value={requirementEditor.accessory_id}
                                    onChange={(accessory_id) =>
                                        setRequirementEditor({
                                            ...requirementEditor,
                                            accessory_id,
                                        })
                                    }
                                />
                                <label>
                                    Количество на изделие
                                    <input
                                        required
                                        type="number"
                                        min="0.001"
                                        step="0.001"
                                        value={
                                            requirementEditor.quantity_per_unit
                                        }
                                        onChange={(event) =>
                                            setRequirementEditor({
                                                ...requirementEditor,
                                                quantity_per_unit:
                                                    event.target.value,
                                            })
                                        }
                                    />
                                </label>
                                <label className={styles.checkField}>
                                    <input
                                        type="checkbox"
                                        checked={requirementEditor.is_optional}
                                        onChange={(event) =>
                                            setRequirementEditor({
                                                ...requirementEditor,
                                                is_optional:
                                                    event.target.checked,
                                            })
                                        }
                                    />
                                    Необязательная фурнитура
                                </label>
                                <label className={styles.fullField}>
                                    Комментарий
                                    <textarea
                                        value={requirementEditor.notes ?? ''}
                                        onChange={(event) =>
                                            setRequirementEditor({
                                                ...requirementEditor,
                                                notes:
                                                    event.target.value || null,
                                            })
                                        }
                                    />
                                </label>
                            </div>
                            {formError && (
                                <p className={styles.error}>{formError}</p>
                            )}
                            <div className={styles.editorActions}>
                                <button
                                    type="button"
                                    onClick={() => setRequirementEditor(null)}
                                >
                                    Отмена
                                </button>
                                <button
                                    className={styles.primaryButton}
                                    disabled={saving}
                                >
                                    Сохранить
                                </button>
                            </div>
                        </form>
                    </AssortmentDialog>
                )}
            </fieldset>
        </section>
    );
}
