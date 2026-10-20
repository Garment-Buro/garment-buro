'use client';

import {
    useCallback,
    useEffect,
    useRef,
    useState,
    type FormEvent,
} from 'react';
import { PiCheck, PiUploadSimple } from 'react-icons/pi';
import { useAssortmentResource } from '@/hooks/production/useAssortmentResource';
import {
    saveAssortment,
    uploadAssortmentMedia,
} from '@/lib/api/productionAssortment';
import {
    readPatternContext,
    readPatternUpload,
    sleeveVariants,
    type PatternContext,
} from '@/lib/production/patternDirectory';
import {
    patternForm,
    patternWrite,
    validPatternGeometry,
    validMeasurement,
    changePatternCode,
    changePatternGeometry,
    variantLabel,
    type PatternForm,
    type PatternPoint,
} from '@/lib/production/patternEditor';
import { compactDecimal } from '@/lib/production/numbers';
import { ReferencePicker } from './ReferencePicker';
import {
    AssortmentDialog,
    FileUploadStatus,
    idleFileUploadStatus,
    type FileUploadStatusValue,
} from './AssortmentDialog';
import styles from '../ProductionAdmin.module.css';

export type PatternTarget = {
    patternId?: number;
    modelId?: number;
    sizeId?: number;
    point?: PatternPoint;
};
export function PatternEditor({
    target,
    onClose,
    onSaved,
    onBusyChange,
}: {
    target: PatternTarget;
    onClose: () => void;
    onSaved: () => void;
    onBusyChange: (busy: boolean) => void;
}) {
    const [modelId, setModelId] = useState(target.modelId ?? 0),
        [sizeId, setSizeId] = useState(target.sizeId ?? 0);
    const [form, setForm] = useState<PatternForm | null>(null),
        [saving, setSaving] = useState(false),
        [uploading, setUploading] = useState(false),
        [error, setError] = useState('');
    const [uploadStatus, setUploadStatus] =
        useState<FileUploadStatusValue>(idleFileUploadStatus);
    const locked = useRef(false);
    const decode = useCallback(
        (value: unknown) => {
            const row = readPatternContext(value);
            if (
                target.patternId
                    ? row.pattern?.id !== target.patternId
                    : row.model.id !== modelId ||
                      row.size?.id !== sizeId ||
                      row.pattern !== null
            )
                throw new Error('Сервер вернул контекст другого лекала.');
            return row;
        },
        [target.patternId, modelId, sizeId],
    );
    const path = target.patternId
        ? `patterns/${target.patternId}`
        : `models/${modelId}/pattern-size/${sizeId}`;
    const source = useAssortmentResource(
        path,
        Boolean(target.patternId || (modelId && sizeId)),
        decode,
    );
    useEffect(() => {
        if (!source.data || !source.data.size) return;
        setForm(
            patternForm(
                source.data,
                source.data.model.id === target.modelId &&
                    source.data.size.id === target.sizeId
                    ? target.point
                    : undefined,
            ),
        );
        setUploadStatus(
            source.data.pattern
                ? { state: 'success', message: 'Файл лекала уже загружен' }
                : idleFileUploadStatus,
        );
    }, [source.data, target.point, target.modelId, target.sizeId]);
    const context = source.data,
        readonly = Boolean(
            context && (!context.model.is_active || !context.size?.is_active),
        );
    const resetChoice = (nextModel: number, nextSize: number) => {
        setModelId(nextModel);
        setSizeId(nextSize);
        setForm(null);
        setError('');
        setUploadStatus(idleFileUploadStatus);
    };
    const submit = async (event: FormEvent) => {
        event.preventDefault();
        if (!form || !context?.size || locked.current) return;
        if (!form.media_object_id) {
            setError('Загрузите файл лекала.');
            return;
        }
        if (!validPatternGeometry(form, context.size)) {
            setError(
                'Выберите ширину, длину и вариант рукава из актуальной сетки размера.',
            );
            return;
        }
        locked.current = true;
        setSaving(true);
        onBusyChange(true);
        setError('');
        try {
            await saveAssortment(
                form.id ? `patterns/${form.id}` : 'patterns',
                form.id ? 'PUT' : 'POST',
                patternWrite(form),
            );
            onSaved();
        } catch (reason) {
            setError(
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось сохранить лекало.',
            );
        } finally {
            locked.current = false;
            setSaving(false);
            onBusyChange(false);
        }
    };
    return (
        <AssortmentDialog
            title={target.patternId ? 'Изменить лекало' : 'Новое лекало'}
            onClose={onClose}
            headerActions={
                form ? (
                    <button
                        type="button"
                        disabled={readonly}
                        aria-pressed={form.is_active}
                        onClick={() =>
                            setForm({ ...form, is_active: !form.is_active })
                        }
                    >
                        {form.is_active ? 'Активно' : 'Скрыто'}
                    </button>
                ) : undefined
            }
        >
            {!target.patternId && (
                <div className={styles.patternIdentityGrid}>
                    <ReferencePicker
                        kind="models"
                        value={modelId}
                        searchLabel="Найти модель лекала"
                        moreLabel="Ещё модели для лекала"
                        onChange={(id) => resetChoice(id, 0)}
                    />
                    {modelId > 0 ? (
                        <ReferencePicker
                            key={modelId}
                            kind="pattern-sizes"
                            modelId={modelId}
                            value={sizeId}
                            onChange={(id) => resetChoice(modelId, id)}
                        />
                    ) : (
                        <p>Сначала выберите модель изделия.</p>
                    )}
                </div>
            )}
            {source.loading && (
                <p role="status">Загружаем размеры и файл лекала…</p>
            )}
            {source.error && (
                <p role="alert">
                    {source.error}{' '}
                    <button type="button" onClick={source.reload}>
                        Повторить загрузку лекала
                    </button>
                </p>
            )}
            {!source.error && form && context?.size && (
                <form className={styles.patternForm} onSubmit={submit}>
                    {readonly && (
                        <p role="status">
                            Модель или размер архивные. Для изменений сначала
                            верните их в активное состояние.
                        </p>
                    )}
                    <fieldset
                        className={styles.adminFields}
                        disabled={readonly || saving || uploading}
                    >
                        <div className={styles.patternIdentityGrid}>
                            <label className={styles.fullField}>
                                Код лекала
                                <input
                                    required
                                    maxLength={64}
                                    value={form.code}
                                    onChange={(event) =>
                                        setForm(
                                            changePatternCode(
                                                form,
                                                event.target.value.toUpperCase(),
                                            ),
                                        )
                                    }
                                />
                                <small>
                                    Латиница, цифры, дефис или подчёркивание
                                </small>
                            </label>
                            {target.patternId && (
                                <>
                                    <label>
                                        Модель
                                        <input
                                            readOnly
                                            value={context.model.name}
                                        />
                                    </label>
                                    <label>
                                        Размер
                                        <input
                                            readOnly
                                            value={context.size.code}
                                        />
                                    </label>
                                </>
                            )}
                        </div>
                        <fieldset className={styles.patternVariantField}>
                            <legend>Вариант лекала</legend>
                            <div className={styles.squareChoiceGrid}>
                                {sleeveVariants(context.size).map((variant) => (
                                    <button
                                        type="button"
                                        key={variant}
                                        data-selected={
                                            form.sleeve_variant === variant
                                        }
                                        aria-pressed={
                                            form.sleeve_variant === variant
                                        }
                                        onClick={() =>
                                            setForm(
                                                changePatternGeometry(
                                                    form,
                                                    context,
                                                    { sleeve_variant: variant },
                                                ),
                                            )
                                        }
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
                            {(['width', 'length'] as const).map((axis) => (
                                <PatternMeasurement
                                    key={axis}
                                    axis={axis}
                                    value={form[`${axis}_cm`]}
                                    context={context}
                                    onChange={(value) =>
                                        setForm(
                                            changePatternGeometry(
                                                form,
                                                context,
                                                { [`${axis}_cm`]: value },
                                            ),
                                        )
                                    }
                                />
                            ))}
                        </div>
                        {!validPatternGeometry(form, context.size) && (
                            <p role="status">
                                Ширина и длина должны соответствовать актуальной
                                сетке с шагом 2 см от минимума размера. Если
                                диапазоны не заданы, заполните их в модели.
                            </p>
                        )}
                        <div className={styles.patternFileField}>
                            <span>Файл лекала</span>
                            <label className={styles.patternFilePicker}>
                                <input
                                    type="file"
                                    accept="application/pdf,image/jpeg,image/png,image/webp"
                                    onChange={async (event) => {
                                        const input = event.currentTarget,
                                            file = input.files?.[0];
                                        if (!file || locked.current) return;
                                        locked.current = true;
                                        setUploading(true);
                                        onBusyChange(true);
                                        setError('');
                                        setUploadStatus({
                                            state: 'uploading',
                                            fileName: file.name,
                                        });
                                        try {
                                            const uploaded = readPatternUpload(
                                                await uploadAssortmentMedia(
                                                    file,
                                                    'pattern',
                                                ),
                                            );
                                            setForm((current) =>
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
                                                    : 'Не удалось загрузить файл.';
                                            setError(message);
                                            setUploadStatus({
                                                state: 'error',
                                                fileName: file.name,
                                                message,
                                            });
                                        } finally {
                                            input.value = '';
                                            locked.current = false;
                                            setUploading(false);
                                            onBusyChange(false);
                                        }
                                    }}
                                />
                                <PiUploadSimple aria-hidden />
                                <span>
                                    {form.filename ??
                                        (form.media_object_id
                                            ? `Медиа №${form.media_object_id}`
                                            : 'PDF, JPEG, PNG или WebP')}
                                </span>
                            </label>
                            <FileUploadStatus value={uploadStatus} />
                        </div>
                    </fieldset>
                    {error && (
                        <p className={styles.error} role="alert">
                            {error}
                        </p>
                    )}
                    <div className={styles.editorActions}>
                        <button type="button" onClick={onClose}>
                            Отмена
                        </button>
                        <button
                            className={styles.primaryButton}
                            disabled={
                                readonly ||
                                saving ||
                                uploading ||
                                !validPatternGeometry(form, context.size)
                            }
                        >
                            {saving ? 'Сохраняем…' : 'Сохранить'}
                        </button>
                    </div>
                </form>
            )}
        </AssortmentDialog>
    );
}

function PatternMeasurement({
    axis,
    value,
    context,
    onChange,
}: {
    axis: 'width' | 'length';
    value: string;
    context: PatternContext;
    onChange: (value: string) => void;
}) {
    const min = context.size?.[`min_${axis}_cm`] ?? null,
        max = context.size?.[`max_${axis}_cm`] ?? null;
    const label = axis === 'width' ? 'Ширина изделия' : 'Длина изделия',
        available = min !== null && max !== null;
    return (
        <section className={styles.patternMeasurement} data-enabled={available}>
            <div className={styles.patternMeasurementHeading}>
                <strong>{label}</strong>
                <output>{value ? `${compactDecimal(value)} см` : '—'}</output>
            </div>
            <label>
                {label}, см
                <input
                    type="number"
                    required
                    min={min ?? undefined}
                    max={max ?? undefined}
                    step="2"
                    value={value}
                    disabled={!available}
                    onChange={(event) => onChange(event.target.value)}
                />
            </label>
            {available ? (
                <div className={styles.patternRangeControl}>
                    <input
                        type="range"
                        min={min}
                        max={max}
                        step="2"
                        value={validMeasurement(value, min, max) ? value : min}
                        aria-label={`${label}, сантиметры`}
                        onChange={(event) => onChange(event.target.value)}
                    />
                    <div className={styles.patternRangeEnds}>
                        <span>{compactDecimal(min)} см</span>
                        <span>{compactDecimal(max)} см</span>
                    </div>
                </div>
            ) : (
                <p>Диапазон не задан для размера.</p>
            )}
        </section>
    );
}
