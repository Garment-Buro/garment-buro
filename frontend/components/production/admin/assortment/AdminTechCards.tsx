'use client';

import { useState, type FormEvent } from 'react';
import {
    PiCheckCircle,
    PiCopy,
    PiPlus,
    PiTrash,
} from 'react-icons/pi';
import { useAssortmentResource } from '@/hooks/production/useAssortmentResource';
import { saveAssortment } from '@/lib/api/productionAssortment';
import {
    employeeStation,
    employeeStations,
    stationLabels,
} from '@/lib/production/adminTypes';
import { compactDecimal } from '@/lib/production/numbers';
import type {
    GarmentModel,
    ReferencePage,
    TechCard,
    TechCheckpoint,
} from '@/lib/production/assortmentTypes';
import { AssortmentDialog, AssortmentFeedback } from './AssortmentDialog';
import styles from '../ProductionAdmin.module.css';

type CardEditor = {
    cardId?: number;
    modelId: number;
    code: string;
    expectedLatestRevision?: number;
    name: string;
    description: string;
    checkpoints: TechCheckpoint[];
};

const newCheckpoint = (position: number): TechCheckpoint => ({
    position,
    stage_code: 'tech',
    role_code: 'tech',
    name: '',
    description: null,
    standard_minutes: null,
    labor_cost: '0',
    currency: 'RUB',
});

export function AdminTechCards() {
    const cardsResource = useAssortmentResource<TechCard[]>('tech-cards');
    const modelsResource =
        useAssortmentResource<ReferencePage<GarmentModel>>('models');
    const [editor, setEditor] = useState<CardEditor | null>(null);
    const [saving, setSaving] = useState(false);
    const [formError, setFormError] = useState('');
    const models = modelsResource.data?.items ?? [];
    const availableModels = models.filter(
        (model) =>
            !(cardsResource.data ?? []).some(
                (card) => card.garment_model_id === model.id,
            ),
    );
    const modelName = (id: number) =>
        models.find((model) => model.id === id)?.name ?? `Модель №${id}`;
    const startCard = () => {
        const model = availableModels[0];
        setEditor({
            modelId: model?.id ?? models[0]?.id ?? 0,
            code: '',
            name: '',
            description: '',
            checkpoints: [newCheckpoint(1)],
        });
    };
    const startRevision = (card: TechCard) => {
        const source = [...card.revisions]
            .filter((revision) => revision.status !== 'discarded')
            .sort((a, b) => b.revision_number - a.revision_number)[0];
        setEditor({
            cardId: card.id,
            modelId: card.garment_model_id,
            code: card.code,
            expectedLatestRevision: card.latest_revision_number,
            name: source?.name_snapshot ?? '',
            description: source?.description_snapshot ?? '',
            checkpoints:
                source?.checkpoints.map((checkpoint, index) => ({
                    ...checkpoint,
                    stage_code: employeeStation(
                        checkpoint.stage_code as Parameters<
                            typeof employeeStation
                        >[0],
                    ),
                    role_code: employeeStation(
                        checkpoint.role_code as Parameters<
                            typeof employeeStation
                        >[0],
                    ),
                    position: index + 1,
                    standard_minutes:
                        checkpoint.standard_minutes == null
                            ? null
                            : compactDecimal(checkpoint.standard_minutes),
                    labor_cost: compactDecimal(checkpoint.labor_cost),
                })) ?? [newCheckpoint(1)],
        });
    };
    const updateCheckpoint = (
        index: number,
        field: keyof TechCheckpoint,
        value: string,
    ) => {
        setEditor((current) => {
            if (!current) return current;
            const checkpoints = [...current.checkpoints];
            checkpoints[index] = {
                ...checkpoints[index],
                [field]: value || null,
            };
            return { ...current, checkpoints };
        });
    };
    const submit = async (event: FormEvent) => {
        event.preventDefault();
        if (!editor) return;
        setSaving(true);
        setFormError('');
        const revision = {
            name: editor.name,
            description: editor.description || null,
            checkpoints: editor.checkpoints.map((checkpoint, index) => ({
                position: index + 1,
                stage_code: checkpoint.stage_code,
                role_code: checkpoint.role_code,
                name: checkpoint.name,
                description: checkpoint.description || null,
                standard_minutes: checkpoint.standard_minutes
                    ? Number(checkpoint.standard_minutes)
                    : null,
                labor_cost: Number(checkpoint.labor_cost || 0),
                currency: 'RUB',
            })),
        };
        try {
            if (editor.cardId) {
                await saveAssortment(
                    `tech-cards/${editor.cardId}/revisions`,
                    'POST',
                    {
                        expected_latest_revision:
                            editor.expectedLatestRevision,
                        revision,
                    },
                );
            } else {
                await saveAssortment(
                    `models/${editor.modelId}/tech-cards`,
                    'POST',
                    { code: editor.code, revision },
                );
            }
            setEditor(null);
            cardsResource.reload();
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось сохранить техкарту',
            );
        } finally {
            setSaving(false);
        }
    };
    const publish = async (card: TechCard, revision: number) => {
        setSaving(true);
        setFormError('');
        try {
            await saveAssortment(
                `tech-cards/${card.id}/revisions/${revision}/publish`,
                'POST',
                {},
            );
            cardsResource.reload();
        } catch (reason) {
            setFormError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось опубликовать версию',
            );
        } finally {
            setSaving(false);
        }
    };

    return (
        <section aria-busy={cardsResource.loading || modelsResource.loading}>
            <div className={styles.assortmentHeading}>
                <div>
                    <h3>Технологические карты</h3>
                    <p className={styles.muted}>
                        Последовательность операций, роли, время и стоимость работ.
                    </p>
                </div>
                <button disabled={!availableModels.length} onClick={startCard}>
                    <PiPlus aria-hidden /> Создать техкарту
                </button>
            </div>
            {formError && !editor && (
                <p className={styles.error} role="alert">
                    {formError}
                </p>
            )}
            <AssortmentFeedback
                loading={cardsResource.loading || modelsResource.loading}
                error={cardsResource.error || modelsResource.error}
                empty={
                    !cardsResource.loading &&
                    !modelsResource.loading &&
                    (cardsResource.data ?? []).length === 0
                }
            />
            <div className={styles.assortmentCards}>
                {(cardsResource.data ?? []).map((card) => {
                    const current = [...card.revisions].sort(
                        (a, b) => b.revision_number - a.revision_number,
                    )[0];
                    const draft = card.revisions.find(
                        (revision) => revision.status === 'draft',
                    );
                    return (
                        <article className={styles.assortmentCard} key={card.id}>
                            <div className={styles.assortmentCardTop}>
                                <div>
                                    <span className={styles.badge}>{card.code}</span>
                                    <h4>{modelName(card.garment_model_id)}</h4>
                                </div>
                                <span className={styles.badge}>
                                    Версия {card.latest_revision_number}
                                </span>
                            </div>
                            <p>{current?.name_snapshot ?? 'Без названия'}</p>
                            <p className={styles.muted}>
                                {current?.checkpoints.length ?? 0} операций ·{' '}
                                {draft ? 'Есть черновик' : 'Черновика нет'}
                            </p>
                            <div className={styles.cardActions}>
                                <button onClick={() => startRevision(card)}>
                                    <PiCopy aria-hidden /> Новая версия
                                </button>
                                {draft && (
                                    <button
                                        className={styles.primaryButton}
                                        disabled={saving}
                                        onClick={() =>
                                            void publish(
                                                card,
                                                draft.revision_number,
                                            )
                                        }
                                    >
                                        <PiCheckCircle aria-hidden /> Опубликовать
                                    </button>
                                )}
                            </div>
                        </article>
                    );
                })}
            </div>
            {editor && (
                <AssortmentDialog
                    title={
                        editor.cardId ? 'Новая версия техкарты' : 'Новая техкарта'
                    }
                    description="Добавляйте операции в фактическом порядке производства и назначайте исполнителя каждой операции."
                    onClose={() => setEditor(null)}
                >
                    <form onSubmit={submit}>
                        <fieldset className={styles.formSection}>
                            <legend>Техкарта</legend>
                            <div className={styles.formGrid}>
                                <label>
                                    Модель
                                    <select
                                        required
                                        disabled={Boolean(editor.cardId)}
                                        value={editor.modelId || ''}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                modelId: Number(event.target.value),
                                            })
                                        }
                                    >
                                        <option value="">Выберите модель</option>
                                        {availableModels.map((model) => (
                                            <option key={model.id} value={model.id}>
                                                {model.name}
                                            </option>
                                        ))}
                                    </select>
                                </label>
                                <label>
                                    Код карты
                                    <input
                                        required
                                        disabled={Boolean(editor.cardId)}
                                        value={editor.code}
                                        placeholder="HOODIE_TECH"
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                code: event.target.value.toUpperCase(),
                                            })
                                        }
                                    />
                                </label>
                                <label className={styles.fullField}>
                                    Название версии
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
                                <label className={styles.fullField}>
                                    Комментарий
                                    <textarea
                                        value={editor.description}
                                        onChange={(event) =>
                                            setEditor({
                                                ...editor,
                                                description: event.target.value,
                                            })
                                        }
                                    />
                                </label>
                            </div>
                        </fieldset>
                        <fieldset className={styles.formSection}>
                            <legend>Операции</legend>
                            <div className={styles.stepList}>
                                {editor.checkpoints.map((checkpoint, index) => (
                                    <article className={styles.stepEditor} key={index}>
                                        <div className={styles.assortmentCardTop}>
                                            <h4>Шаг {index + 1}</h4>
                                            <button
                                                type="button"
                                                className={styles.iconButton}
                                                disabled={
                                                    editor.checkpoints.length === 1
                                                }
                                                onClick={() =>
                                                    setEditor({
                                                        ...editor,
                                                        checkpoints:
                                                            editor.checkpoints.filter(
                                                                (_, itemIndex) =>
                                                                    itemIndex !== index,
                                                            ),
                                                    })
                                                }
                                                aria-label={`Удалить шаг ${index + 1}`}
                                            >
                                                <PiTrash aria-hidden />
                                            </button>
                                        </div>
                                        <div className={styles.formGrid}>
                                            <label>
                                                Участок
                                                <select
                                                    value={checkpoint.stage_code}
                                                    onChange={(event) =>
                                                        updateCheckpoint(
                                                            index,
                                                            'stage_code',
                                                            event.target.value,
                                                        )
                                                    }
                                                >
                                                    {employeeStations.map((station) => (
                                                        <option
                                                            key={station}
                                                            value={station}
                                                        >
                                                            {stationLabels[station]}
                                                        </option>
                                                    ))}
                                                </select>
                                            </label>
                                            <label>
                                                Роль исполнителя
                                                <select
                                                    value={checkpoint.role_code}
                                                    onChange={(event) =>
                                                        updateCheckpoint(
                                                            index,
                                                            'role_code',
                                                            event.target.value,
                                                        )
                                                    }
                                                >
                                                    {employeeStations.map((station) => (
                                                        <option
                                                            key={station}
                                                            value={station}
                                                        >
                                                            {stationLabels[station]}
                                                        </option>
                                                    ))}
                                                </select>
                                            </label>
                                            <label className={styles.fullField}>
                                                Операция
                                                <input
                                                    required
                                                    value={checkpoint.name}
                                                    onChange={(event) =>
                                                        updateCheckpoint(
                                                            index,
                                                            'name',
                                                            event.target.value,
                                                        )
                                                    }
                                                />
                                            </label>
                                            <label>
                                                Норма времени, мин
                                                <input
                                                    type="number"
                                                    min="0.01"
                                                    step="0.01"
                                                    value={
                                                        checkpoint.standard_minutes ??
                                                        ''
                                                    }
                                                    onChange={(event) =>
                                                        updateCheckpoint(
                                                            index,
                                                            'standard_minutes',
                                                            event.target.value,
                                                        )
                                                    }
                                                />
                                            </label>
                                            <label>
                                                Стоимость работы
                                                <input
                                                    type="number"
                                                    min="0"
                                                    step="0.01"
                                                    value={checkpoint.labor_cost}
                                                    onChange={(event) =>
                                                        updateCheckpoint(
                                                            index,
                                                            'labor_cost',
                                                            event.target.value,
                                                        )
                                                    }
                                                />
                                            </label>
                                            <label className={styles.fullField}>
                                                Инструкция
                                                <textarea
                                                    value={
                                                        checkpoint.description ?? ''
                                                    }
                                                    onChange={(event) =>
                                                        updateCheckpoint(
                                                            index,
                                                            'description',
                                                            event.target.value,
                                                        )
                                                    }
                                                />
                                            </label>
                                        </div>
                                    </article>
                                ))}
                            </div>
                            <button
                                type="button"
                                onClick={() =>
                                    setEditor({
                                        ...editor,
                                        checkpoints: [
                                            ...editor.checkpoints,
                                            newCheckpoint(
                                                editor.checkpoints.length + 1,
                                            ),
                                        ],
                                    })
                                }
                            >
                                <PiPlus aria-hidden /> Добавить операцию
                            </button>
                        </fieldset>
                        {formError && <p className={styles.error}>{formError}</p>}
                        <div className={styles.editorActions}>
                            <button type="button" onClick={() => setEditor(null)}>
                                Отмена
                            </button>
                            <button className={styles.primaryButton} disabled={saving}>
                                {saving ? 'Сохраняем…' : 'Сохранить черновик'}
                            </button>
                        </div>
                    </form>
                </AssortmentDialog>
            )}
        </section>
    );
}
