'use client';

import { useMemo, useState, type FormEvent } from 'react';
import { PiPencilSimple, PiPlus, PiUploadSimple } from 'react-icons/pi';
import { useAssortmentResource } from '@/hooks/production/useAssortmentResource';
import {
    saveAssortment,
    uploadAssortmentMedia,
} from '@/lib/api/productionAssortment';
import type {
    GarmentModel,
    Pattern,
    ReferencePage,
} from '@/lib/production/assortmentTypes';
import { AdminFilters } from '../AdminFilters';
import { AssortmentDialog, AssortmentFeedback } from './AssortmentDialog';
import styles from '../ProductionAdmin.module.css';

type PatternForm = Omit<Pattern, 'id' | 'version' | 'grid_key'> & {
    id?: number;
    version?: number;
    filename?: string;
};

const emptyPattern = (model?: GarmentModel): PatternForm => ({
    code: '',
    garment_model_id: model?.id ?? 0,
    garment_size_id: model?.sizes[0]?.id ?? 0,
    media_object_id: 0,
    name: '',
    width_cm: '',
    length_cm: '',
    sleeve_length_cm: null,
    height_cm: null,
    is_active: true,
});

export function AdminPatterns() {
    const patternsResource = useAssortmentResource<Pattern[]>('patterns');
    const modelsResource =
        useAssortmentResource<ReferencePage<GarmentModel>>('models');
    const [modelFilter, setModelFilter] = useState(0);
    const [query, setQuery] = useState('');
    const [editor, setEditor] = useState<PatternForm | null>(null);
    const [saving, setSaving] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [formError, setFormError] = useState('');
    const patterns = useMemo(
        () =>
            (patternsResource.data ?? []).filter((item) => {
                const matchesModel =
                    !modelFilter || item.garment_model_id === modelFilter;
                const needle = query.trim().toLowerCase();
                return (
                    matchesModel &&
                    (!needle ||
                        `${item.code} ${item.name} ${item.grid_key}`
                            .toLowerCase()
                            .includes(needle))
                );
            }),
        [modelFilter, patternsResource.data, query],
    );
    const models = modelsResource.data?.items ?? [];
    const modelName = (id: number) =>
        models.find((model) => model.id === id)?.name ?? `Модель №${id}`;
    const sizeName = (modelId: number, sizeId: number) =>
        models
            .find((model) => model.id === modelId)
            ?.sizes.find((size) => size.id === sizeId)?.code ?? `№${sizeId}`;

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
                    name: editor.name,
                    width_cm: Number(editor.width_cm),
                    length_cm: Number(editor.length_cm),
                    sleeve_length_cm: editor.sleeve_length_cm
                        ? Number(editor.sleeve_length_cm)
                        : null,
                    height_cm: editor.height_cm
                        ? Number(editor.height_cm)
                        : null,
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
                    <h3>Лекала</h3>
                    <p className={styles.muted}>
                        Файл для каждой точки размерной сетки с шагом два сантиметра.
                    </p>
                </div>
                <button
                    disabled={!models.length}
                    onClick={() => setEditor(emptyPattern(models[0]))}
                >
                    <PiPlus aria-hidden /> Добавить лекало
                </button>
            </div>
            <div className={styles.assortmentFilters}>
                <label className={styles.assortmentSearch}>
                    Поиск по коду или названию
                    <input
                        type="search"
                        value={query}
                        placeholder="Например, PAT-HOODIE-M"
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
                    ]}
                    values={{ model: String(modelFilter) }}
                    defaults={{ model: '0' }}
                    onApply={(values) =>
                        setModelFilter(Number(values.model))
                    }
                />
            </div>
            <AssortmentFeedback
                loading={patternsResource.loading || modelsResource.loading}
                error={patternsResource.error || modelsResource.error}
                empty={
                    !patternsResource.loading &&
                    !modelsResource.loading &&
                    patterns.length === 0
                }
            />
            {patterns.length > 0 && (
                <div className={styles.assortmentCards}>
                    {patterns.map((pattern) => (
                        <article className={styles.assortmentCard} key={pattern.id}>
                            <div className={styles.assortmentCardTop}>
                                <div>
                                    <span className={styles.badge}>
                                        {sizeName(
                                            pattern.garment_model_id,
                                            pattern.garment_size_id,
                                        )}
                                    </span>
                                    <small>{pattern.code}</small>
                                    <h4>{pattern.name}</h4>
                                </div>
                                <button
                                    className={styles.iconButton}
                                    onClick={() => setEditor({ ...pattern })}
                                    aria-label={`Изменить лекало ${pattern.name}`}
                                >
                                    <PiPencilSimple aria-hidden />
                                </button>
                            </div>
                            <p>{modelName(pattern.garment_model_id)}</p>
                            <dl className={styles.compactFacts}>
                                <div>
                                    <dt>Ширина</dt>
                                    <dd>{pattern.width_cm} см</dd>
                                </div>
                                <div>
                                    <dt>Длина</dt>
                                    <dd>{pattern.length_cm} см</dd>
                                </div>
                                <div>
                                    <dt>Файл</dt>
                                    <dd>№{pattern.media_object_id}</dd>
                                </div>
                            </dl>
                        </article>
                    ))}
                </div>
            )}
            {editor && (
                <AssortmentDialog
                    title={editor.id ? 'Изменить лекало' : 'Новое лекало'}
                    description="Ширина и длина должны попадать в диапазон размера и сетку с шагом два сантиметра."
                    onClose={() => setEditor(null)}
                >
                    <form onSubmit={submit}>
                        <div className={styles.formGrid}>
                            <label className={styles.fullField}>
                                Код лекала
                                <input
                                    required
                                    maxLength={64}
                                    value={editor.code}
                                    placeholder="PAT-HOODIE-M-001"
                                    onChange={(event) =>
                                        setEditor({
                                            ...editor,
                                            code: event.target.value.toUpperCase(),
                                        })
                                    }
                                />
                                <small>Латиница, цифры, дефис или подчёркивание.</small>
                            </label>
                            <label>
                                Модель
                                <select
                                    required
                                    value={editor.garment_model_id || ''}
                                    onChange={(event) => {
                                        const model = models.find(
                                            (item) =>
                                                item.id === Number(event.target.value),
                                        );
                                        setEditor({
                                            ...editor,
                                            garment_model_id: model?.id ?? 0,
                                            garment_size_id:
                                                model?.sizes[0]?.id ?? 0,
                                        });
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
                                    value={editor.garment_size_id || ''}
                                    onChange={(event) =>
                                        setEditor({
                                            ...editor,
                                            garment_size_id: Number(
                                                event.target.value,
                                            ),
                                        })
                                    }
                                >
                                    <option value="">Выберите размер</option>
                                    {(
                                        models.find(
                                            (model) =>
                                                model.id ===
                                                editor.garment_model_id,
                                        )?.sizes ?? []
                                    ).map((size) => (
                                        <option key={size.id} value={size.id}>
                                            {size.code}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label className={styles.fullField}>
                                Название
                                <input
                                    required
                                    value={editor.name}
                                    placeholder="M 46×70, рукав 22"
                                    onChange={(event) =>
                                        setEditor({
                                            ...editor,
                                            name: event.target.value,
                                        })
                                    }
                                />
                            </label>
                            {(
                                [
                                    ['width_cm', 'Ширина, см'],
                                    ['length_cm', 'Длина, см'],
                                    ['sleeve_length_cm', 'Рукав, см'],
                                    ['height_cm', 'Рост, см'],
                                ] as const
                            ).map(([field, label], index) => (
                                <label key={field}>
                                    {label}
                                    <input
                                        required={index < 2}
                                        type="number"
                                        min="0.01"
                                        step="0.01"
                                        value={editor[field] ?? ''}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                [field]: event.target.value || null,
                                            })
                                        }
                                    />
                                </label>
                            ))}
                            <label className={styles.fullField}>
                                Файл лекала
                                <input
                                    type="file"
                                    accept="application/pdf,image/jpeg,image/png,image/webp"
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
                                        } catch (reason) {
                                            setFormError(
                                                reason instanceof Error
                                                    ? reason.message
                                                    : 'Не удалось загрузить файл',
                                            );
                                        } finally {
                                            setUploading(false);
                                        }
                                    }}
                                />
                                <small>
                                    <PiUploadSimple aria-hidden />{' '}
                                    {editor.filename ??
                                        (editor.media_object_id
                                            ? `Медиа №${editor.media_object_id}`
                                            : 'PDF, JPEG, PNG или WebP')}
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
                                Лекало активно
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
                                {saving ? 'Сохраняем…' : 'Сохранить лекало'}
                            </button>
                        </div>
                    </form>
                </AssortmentDialog>
            )}
        </section>
    );
}
