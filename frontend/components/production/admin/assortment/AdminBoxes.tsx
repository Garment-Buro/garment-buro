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
    GarmentModel,
    PackagingBox,
    PackagingRule,
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

type BoxForm = Partial<PackagingBox> & {
    code: string;
    name: string;
    inner_length_cm: string;
    inner_width_cm: string;
    inner_height_cm: string;
    max_items: number;
    unit_cost: string;
    stock_quantity: number;
    minimum_stock_quantity: number;
    photo_media_object_id: number | null;
    is_active: boolean;
};
type RuleForm = Partial<PackagingRule> & {
    garment_model_id: number;
    box_id: number;
    max_items: number;
    priority: number;
};

export function AdminBoxes() {
    const boxes = useAssortmentResource<PackagingBox[]>('boxes');
    const rules = useAssortmentResource<PackagingRule[]>('packaging-rules');
    const models = useAssortmentResource<ReferencePage<GarmentModel>>('models');
    const [editor, setEditor] = useState<BoxForm | null>(null);
    const [ruleEditor, setRuleEditor] = useState<RuleForm | null>(null);
    const [saving, setSaving] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] =
        useState<FileUploadStatusValue>(idleFileUploadStatus);
    const [formError, setFormError] = useState('');
    const boxName = (id: number) =>
        boxes.data?.find((box) => box.id === id)?.name ?? `№${id}`;
    const modelName = (id: number) =>
        models.data?.items.find((model) => model.id === id)?.name ?? `№${id}`;

    const submitBox = async (event: FormEvent) => {
        event.preventDefault();
        if (!editor) return;
        setSaving(true);
        setFormError('');
        try {
            await saveAssortment(
                editor.id ? `boxes/${editor.id}` : 'boxes',
                editor.id ? 'PUT' : 'POST',
                {
                    code: editor.code,
                    name: editor.name,
                    inner_length_cm: Number(editor.inner_length_cm),
                    inner_width_cm: Number(editor.inner_width_cm),
                    inner_height_cm: Number(editor.inner_height_cm),
                    max_items: Number(editor.max_items),
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
            );
            setEditor(null);
            boxes.reload();
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось сохранить коробку',
            );
        } finally {
            setSaving(false);
        }
    };
    const submitRule = async (event: FormEvent) => {
        event.preventDefault();
        if (!ruleEditor) return;
        setSaving(true);
        setFormError('');
        try {
            await saveAssortment(
                ruleEditor.id
                    ? `packaging-rules/${ruleEditor.id}`
                    : 'packaging-rules',
                ruleEditor.id ? 'PUT' : 'POST',
                {
                    garment_model_id: ruleEditor.garment_model_id,
                    box_id: ruleEditor.box_id,
                    max_items: Number(ruleEditor.max_items),
                    priority: Number(ruleEditor.priority),
                    ...(ruleEditor.id
                        ? { expected_version: ruleEditor.version }
                        : {}),
                },
            );
            setRuleEditor(null);
            rules.reload();
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось сохранить правило упаковки',
            );
        } finally {
            setSaving(false);
        }
    };

    return (
        <section aria-busy={boxes.loading}>
            <div className={styles.assortmentHeading}>
                <div>
                    <h3>Коробки</h3>
                    <p className={styles.muted}>
                        Габариты, вместимость, остатки и подбор упаковки для моделей.
                    </p>
                </div>
                <div className={styles.headingActions}>
                    <button
                        disabled={!boxes.data?.length || !models.data?.items.length}
                        onClick={() =>
                            setRuleEditor({
                                garment_model_id: models.data?.items[0]?.id ?? 0,
                                box_id: boxes.data?.[0]?.id ?? 0,
                                max_items: 1,
                                priority: 0,
                            })
                        }
                    >
                        <PiLink aria-hidden /> Правило упаковки
                    </button>
                    <button
                        onClick={() => {
                            setUploadStatus(idleFileUploadStatus);
                            setEditor({
                                code: '',
                                name: '',
                                inner_length_cm: '',
                                inner_width_cm: '',
                                inner_height_cm: '',
                                max_items: 1,
                                unit_cost: '0',
                                stock_quantity: 0,
                                minimum_stock_quantity: 0,
                                photo_media_object_id: null,
                                is_active: true,
                            });
                        }}
                    >
                        <PiPlus aria-hidden /> Добавить коробку
                    </button>
                </div>
            </div>
            <AssortmentFeedback
                loading={boxes.loading}
                error={boxes.error}
                empty={!boxes.loading && (boxes.data ?? []).length === 0}
            />
            <div className={styles.assortmentCards}>
                {(boxes.data ?? []).map((box) => (
                    <article className={styles.assortmentCard} key={box.id}>
                        <div className={styles.assortmentCardTop}>
                            <div>
                                <span className={styles.badge}>{box.code}</span>
                                <h4>{box.name}</h4>
                            </div>
                            <button
                                className={styles.iconButton}
                                onClick={() => {
                                    setUploadStatus(
                                        box.photo_media_object_id
                                            ? {
                                                  state: 'success',
                                                  message:
                                                      'Фото коробки уже загружено',
                                              }
                                            : idleFileUploadStatus,
                                    );
                                    setEditor({
                                        ...box,
                                        inner_length_cm: compactDecimal(
                                            box.inner_length_cm,
                                        ),
                                        inner_width_cm: compactDecimal(
                                            box.inner_width_cm,
                                        ),
                                        inner_height_cm: compactDecimal(
                                            box.inner_height_cm,
                                        ),
                                        unit_cost: compactDecimal(box.unit_cost),
                                    });
                                }}
                                aria-label={`Изменить коробку ${box.name}`}
                            >
                                <PiPencilSimple aria-hidden />
                            </button>
                        </div>
                        <p>
                            {compactDecimal(box.inner_length_cm)} ×{' '}
                            {compactDecimal(box.inner_width_cm)} ×{' '}
                            {compactDecimal(box.inner_height_cm)} см
                        </p>
                        <dl className={styles.compactFacts}>
                            <div>
                                <dt>Вместимость</dt>
                                <dd>{box.max_items} шт.</dd>
                            </div>
                            <div>
                                <dt>Остаток</dt>
                                <dd>{box.stock_quantity}</dd>
                            </div>
                            <div>
                                <dt>Цена</dt>
                                <dd>{compactDecimal(box.unit_cost)} ₽</dd>
                            </div>
                        </dl>
                    </article>
                ))}
            </div>
            {(rules.data ?? []).length > 0 && (
                <section className={styles.relatedSection}>
                    <h4>Правила упаковки</h4>
                    <div className={styles.relationshipList}>
                        {(rules.data ?? []).map((rule) => (
                            <button
                                key={rule.id}
                                className={styles.relationshipCard}
                                onClick={() => setRuleEditor({ ...rule })}
                            >
                                <span>
                                    <strong>{modelName(rule.garment_model_id)}</strong>
                                    <small>{boxName(rule.box_id)}</small>
                                </span>
                                <span>
                                    до {rule.max_items} шт. · очередь {rule.priority + 1}
                                </span>
                            </button>
                        ))}
                    </div>
                </section>
            )}
            {editor && (
                <AssortmentDialog
                    title={editor.id ? 'Изменить коробку' : 'Новая коробка'}
                    onClose={() => setEditor(null)}
                >
                    <form onSubmit={submitBox}>
                        <div className={styles.formGrid}>
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
                            {(
                                [
                                    ['inner_length_cm', 'Длина внутри, см'],
                                    ['inner_width_cm', 'Ширина внутри, см'],
                                    ['inner_height_cm', 'Высота внутри, см'],
                                ] as const
                            ).map(([field, label]) => (
                                <label key={field}>
                                    {label}
                                    <input
                                        required
                                        type="number"
                                        min="0.01"
                                        step="0.01"
                                        value={editor[field]}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                [field]: event.target.value,
                                            })
                                        }
                                    />
                                </label>
                            ))}
                            <label>
                                Вместимость, шт.
                                <input
                                    required
                                    type="number"
                                    min="1"
                                    value={editor.max_items}
                                    onChange={(event) =>
                                        setEditor({
                                            ...editor,
                                            max_items: Number(event.target.value),
                                        })
                                    }
                                />
                            </label>
                            <label>
                                Цена
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
                                <span>Фото коробки</span>
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
                                Коробка доступна
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
            {ruleEditor && (
                <AssortmentDialog
                    title="Правило упаковки"
                    description="Укажите, сколько изделий выбранной модели помещается в конкретную коробку. Если коробок несколько, меньшее число означает более высокий приоритет."
                    onClose={() => setRuleEditor(null)}
                >
                    <form onSubmit={submitRule}>
                        <div className={styles.packagingRuleGuide}>
                            <span>Модель</span>
                            <strong aria-hidden>→</strong>
                            <span>Коробка</span>
                            <strong aria-hidden>→</strong>
                            <span>Количество</span>
                        </div>
                        <div className={styles.formGrid}>
                            <label>
                                Модель
                                <select
                                    required
                                    value={ruleEditor.garment_model_id || ''}
                                    onChange={(event) =>
                                        setRuleEditor({
                                            ...ruleEditor,
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
                                Коробка
                                <select
                                    required
                                    value={ruleEditor.box_id || ''}
                                    onChange={(event) => {
                                        const box = boxes.data?.find(
                                            (item) =>
                                                item.id === Number(event.target.value),
                                        );
                                        setRuleEditor({
                                            ...ruleEditor,
                                            box_id: box?.id ?? 0,
                                            max_items: Math.min(
                                                ruleEditor.max_items,
                                                box?.max_items ?? 1,
                                            ),
                                        });
                                    }}
                                >
                                    <option value="">Выберите коробку</option>
                                    {(boxes.data ?? []).map((box) => (
                                        <option key={box.id} value={box.id}>
                                            {box.name}, до {box.max_items} шт.
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label>
                                Максимум изделий этой модели
                                <input
                                    required
                                    type="number"
                                    min="1"
                                    max={
                                        boxes.data?.find(
                                            (box) => box.id === ruleEditor.box_id,
                                        )?.max_items
                                    }
                                    value={ruleEditor.max_items}
                                    onChange={(event) =>
                                        setRuleEditor({
                                            ...ruleEditor,
                                            max_items: Number(event.target.value),
                                        })
                                    }
                                />
                            </label>
                            <label>
                                Очередь выбора
                                <input
                                    type="number"
                                    min="0"
                                    value={ruleEditor.priority}
                                    onChange={(event) =>
                                        setRuleEditor({
                                            ...ruleEditor,
                                            priority: Number(event.target.value),
                                        })
                                    }
                                />
                                <small>0 — основная коробка, 1 и далее — запасные.</small>
                            </label>
                        </div>
                        {formError && <p className={styles.error}>{formError}</p>}
                        <div className={styles.editorActions}>
                            <button type="button" onClick={() => setRuleEditor(null)}>
                                Отмена
                            </button>
                            <button className={styles.primaryButton} disabled={saving}>
                                Сохранить правило
                            </button>
                        </div>
                    </form>
                </AssortmentDialog>
            )}
        </section>
    );
}
