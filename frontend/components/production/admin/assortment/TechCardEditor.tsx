'use client';

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { PiPlus, PiTrash } from 'react-icons/pi';
import { saveAssortment } from '@/lib/api/productionAssortment';
import { employeeStations, stationLabels } from '@/lib/production/adminTypes';
import { requestTechCardSource } from '@/lib/production/techDirectory';
import {
    newTechCheckpoint,
    techCardForm,
    techCardWrite,
    type TechCardForm,
} from '@/lib/production/techCardEditor';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import { ReferencePicker } from './ReferencePicker';
import { AssortmentDialog } from './AssortmentDialog';
import styles from '../ProductionAdmin.module.css';

const stationOptions = (current: string) => [
    ...new Set([current, ...employeeStations]),
];
const stationLabel = (station: string) => {
    const label = (stationLabels as Record<string, string>)[station] ?? station;
    return (employeeStations as readonly string[]).includes(station)
        ? label
        : `${label} · сохранённое назначение`;
};

/** One mounted editor owns a single source read and its draft; the list never contains operations. */
export function TechCardEditor({
    cardId,
    onClose,
    onSaved,
    onBusyChange,
}: {
    cardId: number;
    onClose: () => void;
    onSaved: () => void;
    onBusyChange: (busy: boolean) => void;
}) {
    const [editor, setEditor] = useState<TechCardForm | null>(() =>
        cardId ? null : techCardForm(),
    );
    const [loadError, setLoadError] = useState('');
    const [revision, setRevision] = useState(0);
    const [saving, setSaving] = useState(false);
    const [formError, setFormError] = useState('');
    const writeLocked = useRef(false);
    const epoch = useProductionAuthStore((state) => state.sessionEpoch);
    useEffect(() => {
        if (!cardId) return;
        const controller = new AbortController();
        void useProductionAuthStore
            .getState()
            .runAuthenticated(() =>
                requestTechCardSource(cardId, controller.signal),
            )
            .then((row) => {
                if (controller.signal.aborted) return;
                if (row.draft_revision_number !== null)
                    throw new Error(
                        'У техкарты уже есть черновик. Сначала опубликуйте или отклоните его.',
                    );
                setEditor(techCardForm(row));
            })
            .catch((error) => {
                if (!controller.signal.aborted)
                    setLoadError(
                        error instanceof Error
                            ? error.message
                            : 'Не удалось прочитать исходную версию.',
                    );
            });
        return () => controller.abort();
    }, [cardId, epoch, revision]);
    const updateCheckpoint = (
        index: number,
        field:
            | 'stage_code'
            | 'role_code'
            | 'name'
            | 'description'
            | 'standard_minutes'
            | 'labor_cost',
        value: string,
    ) => {
        setEditor((current) => {
            if (!current) return current;
            const checkpoints = [...current.checkpoints];
            checkpoints[index] = {
                ...checkpoints[index],
                [field]: ['description', 'standard_minutes'].includes(field)
                    ? value || null
                    : value,
            };
            return { ...current, checkpoints };
        });
    };
    const submit = async (event: FormEvent) => {
        event.preventDefault();
        if (!editor || writeLocked.current) return;
        writeLocked.current = true;
        setSaving(true);
        onBusyChange(true);
        setFormError('');
        try {
            const write = techCardWrite(editor);
            await saveAssortment(write.path, 'POST', write.payload);
            onSaved();
        } catch (error) {
            setFormError(
                error instanceof Error
                    ? error.message
                    : 'Не удалось сохранить техкарту.',
            );
        } finally {
            writeLocked.current = false;
            setSaving(false);
            onBusyChange(false);
        }
    };
    return (
        <AssortmentDialog
            title={cardId ? 'Новая версия техкарты' : 'Новая техкарта'}
            description="Добавляйте операции в фактическом порядке производства и назначайте исполнителя каждой операции."
            onClose={onClose}
        >
            {!editor && !loadError && (
                <p role="status">Загружаем исходную версию…</p>
            )}
            {loadError && (
                <p role="alert">
                    {loadError}{' '}
                    <button
                        type="button"
                        onClick={() => {
                            setLoadError('');
                            setRevision((value) => value + 1);
                        }}
                    >
                        Повторить загрузку техкарты
                    </button>
                </p>
            )}
            {editor && (
                <>
                    <form onSubmit={submit}>
                        <fieldset className={styles.formSection}>
                            <legend>Техкарта</legend>
                            <div className={styles.formGrid}>
                                {editor.cardId ? (
                                    <label>
                                        Модель
                                        <input
                                            readOnly
                                            value={editor.modelName}
                                        />
                                    </label>
                                ) : (
                                    <ReferencePicker
                                        kind="tech-card-models"
                                        value={editor.modelId}
                                        onChange={(modelId, row) =>
                                            setEditor({
                                                ...editor,
                                                modelId,
                                                modelName: row?.name ?? '',
                                            })
                                        }
                                    />
                                )}
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
                                    <article
                                        className={styles.stepEditor}
                                        key={index}
                                    >
                                        <div
                                            className={styles.assortmentCardTop}
                                        >
                                            <h4>Шаг {index + 1}</h4>
                                            <button
                                                type="button"
                                                className={styles.iconButton}
                                                disabled={
                                                    editor.checkpoints
                                                        .length === 1
                                                }
                                                onClick={() =>
                                                    setEditor({
                                                        ...editor,
                                                        checkpoints:
                                                            editor.checkpoints.filter(
                                                                (
                                                                    _,
                                                                    itemIndex,
                                                                ) =>
                                                                    itemIndex !==
                                                                    index,
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
                                                    value={
                                                        checkpoint.stage_code
                                                    }
                                                    onChange={(event) =>
                                                        updateCheckpoint(
                                                            index,
                                                            'stage_code',
                                                            event.target.value,
                                                        )
                                                    }
                                                >
                                                    {stationOptions(
                                                        checkpoint.stage_code,
                                                    ).map((station) => (
                                                        <option
                                                            key={station}
                                                            value={station}
                                                        >
                                                            {stationLabel(
                                                                station,
                                                            )}
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
                                                    {stationOptions(
                                                        checkpoint.role_code,
                                                    ).map((station) => (
                                                        <option
                                                            key={station}
                                                            value={station}
                                                        >
                                                            {stationLabel(
                                                                station,
                                                            )}
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
                                                    value={
                                                        checkpoint.labor_cost
                                                    }
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
                                                        checkpoint.description ??
                                                        ''
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
                                disabled={editor.checkpoints.length >= 200}
                                onClick={() =>
                                    setEditor({
                                        ...editor,
                                        checkpoints: [
                                            ...editor.checkpoints,
                                            newTechCheckpoint(
                                                editor.checkpoints.length + 1,
                                            ),
                                        ],
                                    })
                                }
                            >
                                <PiPlus aria-hidden /> Добавить операцию
                            </button>
                        </fieldset>
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
                                disabled={saving}
                            >
                                {saving ? 'Сохраняем…' : 'Сохранить черновик'}
                            </button>
                        </div>
                    </form>
                </>
            )}
        </AssortmentDialog>
    );
}
