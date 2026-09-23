'use client';

import { useState, type FormEvent } from 'react';
import {
    PiLink,
    PiPencilSimple,
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
    Accessory,
    AccessoryCategory,
    AccessoryRequirement,
    GarmentModel,
    ReferencePage,
} from '@/lib/production/assortmentTypes';
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
    const accessories = useAssortmentResource<Accessory[]>('accessories');
    const categories =
        useAssortmentResource<AccessoryCategory[]>('accessory-categories');
    const requirements = useAssortmentResource<AccessoryRequirement[]>(
        'accessory-requirements',
    );
    const models = useAssortmentResource<ReferencePage<GarmentModel>>('models');
    const [categoryEditor, setCategoryEditor] = useState<CategoryForm | null>(null);
    const [editor, setEditor] = useState<AccessoryForm | null>(null);
    const [requirementEditor, setRequirementEditor] =
        useState<RequirementForm | null>(null);
    const [saving, setSaving] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] =
        useState<FileUploadStatusValue>(idleFileUploadStatus);
    const [formError, setFormError] = useState('');
    const categoryName = (id: number) =>
        categories.data?.find((item) => item.id === id)?.name ?? `№${id}`;
    const accessoryName = (id: number) =>
        accessories.data?.find((item) => item.id === id)?.name ?? `№${id}`;
    const modelName = (id: number) =>
        models.data?.items.find((item) => item.id === id)?.name ?? `№${id}`;

    const runSave = async (
        path: string,
        method: 'POST' | 'PUT',
        payload: unknown,
        done: () => void,
    ) => {
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
                setCategoryEditor(null);
                categories.reload();
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
                minimum_stock_quantity: Number(
                    editor.minimum_stock_quantity,
                ),
                photo_media_object_id: editor.photo_media_object_id,
                is_active: editor.is_active,
                ...(editor.id ? { expected_version: editor.version } : {}),
            },
            () => {
                setEditor(null);
                accessories.reload();
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
                quantity_per_unit: Number(
                    requirementEditor.quantity_per_unit,
                ),
                is_optional: requirementEditor.is_optional,
                notes: requirementEditor.notes,
                ...(requirementEditor.id
                    ? { expected_version: requirementEditor.version }
                    : {}),
            },
            () => {
                setRequirementEditor(null);
                requirements.reload();
                accessories.reload();
            },
        );
    };

    return (
        <section aria-busy={accessories.loading || categories.loading}>
            <div className={styles.assortmentHeading}>
                <div>
                    <h3>Фурнитура</h3>
                    <p className={styles.muted}>
                        Категории, остатки и применимость фурнитуры к моделям.
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
                        disabled={!categories.data?.length}
                        onClick={() => {
                            setUploadStatus(idleFileUploadStatus);
                            setEditor({
                                category_id: categories.data?.[0]?.id ?? 0,
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
            <div className={styles.chipList} aria-label="Категории фурнитуры">
                {(categories.data ?? []).map((category) => (
                    <button
                        key={category.id}
                        onClick={() => setCategoryEditor({ ...category })}
                    >
                        {category.name}
                    </button>
                ))}
            </div>
            <AssortmentFeedback
                loading={accessories.loading || categories.loading}
                error={accessories.error || categories.error}
                empty={
                    !accessories.loading &&
                    !categories.loading &&
                    (accessories.data ?? []).length === 0
                }
            />
            <div className={styles.assortmentCards}>
                {(accessories.data ?? []).map((item) => (
                    <article className={styles.assortmentCard} key={item.id}>
                        <div className={styles.assortmentCardTop}>
                            <div>
                                <span className={styles.badge}>
                                    {categoryName(item.category_id)}
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
                                        unit_cost: compactDecimal(item.unit_cost),
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
                            {item.model_ids.length
                                ? `Подходит для ${item.model_ids.length} моделей`
                                : 'Модели пока не назначены'}
                        </p>
                        <button
                            disabled={!models.data?.items.length}
                            onClick={() =>
                                setRequirementEditor({
                                    garment_model_id:
                                        models.data?.items[0]?.id ?? 0,
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
            {(requirements.data ?? []).length > 0 && (
                <section className={styles.relatedSection}>
                    <h4>Применимость и расход</h4>
                    <div className={styles.relationshipList}>
                        {(requirements.data ?? []).map((item) => (
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
                                    <strong>{accessoryName(item.accessory_id)}</strong>
                                    <small>{modelName(item.garment_model_id)}</small>
                                </span>
                                <span>
                                    {compactDecimal(item.quantity_per_unit)} шт.
                                </span>
                            </button>
                        ))}
                    </div>
                </section>
            )}
            {categoryEditor && (
                <AssortmentDialog
                    title={categoryEditor.id ? 'Изменить категорию' : 'Новая категория'}
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
                                            description: event.target.value || null,
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
                        {formError && <p className={styles.error}>{formError}</p>}
                        <div className={styles.editorActions}>
                            <button type="button" onClick={() => setCategoryEditor(null)}>
                                Отмена
                            </button>
                            <button className={styles.primaryButton} disabled={saving}>
                                Сохранить
                            </button>
                        </div>
                    </form>
                </AssortmentDialog>
            )}
            {editor && (
                <AssortmentDialog
                    title={editor.id ? 'Изменить фурнитуру' : 'Новая фурнитура'}
                    onClose={() => setEditor(null)}
                >
                    <form onSubmit={submitAccessory}>
                        <div className={styles.formGrid}>
                            <label>
                                Категория
                                <select
                                    required
                                    value={editor.category_id || ''}
                                    onChange={(event) =>
                                        setEditor({
                                            ...editor,
                                            category_id: Number(event.target.value),
                                        })
                                    }
                                >
                                    <option value="">Выберите категорию</option>
                                    {(categories.data ?? []).map((category) => (
                                        <option key={category.id} value={category.id}>
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
                                        setEditor({ ...editor, name: event.target.value })
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
                                            stock_quantity: Number(event.target.value),
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
                                        const file = event.target.files?.[0];
                                        if (!file) return;
                                        setUploading(true);
                                        setFormError('');
                                        setUploadStatus({
                                            state: 'uploading',
                                            fileName: file.name,
                                        });
                                        try {
                                            const media = await uploadAssortmentMedia(
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
                        {formError && <p className={styles.error}>{formError}</p>}
                        <div className={styles.editorActions}>
                            <button type="button" onClick={() => setEditor(null)}>
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
                            <label>
                                Модель
                                <select
                                    required
                                    value={requirementEditor.garment_model_id || ''}
                                    onChange={(event) =>
                                        setRequirementEditor({
                                            ...requirementEditor,
                                            garment_model_id: Number(event.target.value),
                                        })
                                    }
                                >
                                    <option value="">Выберите модель</option>
                                    {(models.data?.items ?? []).map((model) => (
                                        <option key={model.id} value={model.id}>
                                            {model.name}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label>
                                Фурнитура
                                <select
                                    required
                                    value={requirementEditor.accessory_id || ''}
                                    onChange={(event) =>
                                        setRequirementEditor({
                                            ...requirementEditor,
                                            accessory_id: Number(event.target.value),
                                        })
                                    }
                                >
                                    <option value="">Выберите фурнитуру</option>
                                    {(accessories.data ?? []).map((item) => (
                                        <option key={item.id} value={item.id}>
                                            {item.name}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label>
                                Количество на изделие
                                <input
                                    required
                                    type="number"
                                    min="0.1"
                                    step="0.1"
                                    value={requirementEditor.quantity_per_unit}
                                    onChange={(event) =>
                                        setRequirementEditor({
                                            ...requirementEditor,
                                            quantity_per_unit: event.target.value,
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
                                            is_optional: event.target.checked,
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
                                            notes: event.target.value || null,
                                        })
                                    }
                                />
                            </label>
                        </div>
                        {formError && <p className={styles.error}>{formError}</p>}
                        <div className={styles.editorActions}>
                            <button
                                type="button"
                                onClick={() => setRequirementEditor(null)}
                            >
                                Отмена
                            </button>
                            <button className={styles.primaryButton} disabled={saving}>
                                Сохранить
                            </button>
                        </div>
                    </form>
                </AssortmentDialog>
            )}
        </section>
    );
}
