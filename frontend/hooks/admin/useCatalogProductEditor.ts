import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ApiError } from '@/lib/api/http';
import type {
    CatalogEditorClient,
    EditorFabric,
    EditorModel,
} from '@/lib/products/editorClient';
import {
    buildPresetPayload,
    emptyPresetEditor,
    type PresetEditor,
} from '@/lib/production/presetEditor';

export function useCatalogProductEditor(
    client: CatalogEditorClient,
    id: number | null,
    onSaved: () => void,
) {
    const operation = useRef<'save' | 'upload' | 'confirmed' | null>(null);
    const alive = useRef(true);
    useEffect(() => {
        alive.current = true;
        return () => {
            alive.current = false;
        };
    }, []);
    const [editor, setEditor] = useState<PresetEditor | null>(null);
    const [loading, setLoading] = useState(true),
        [error, setError] = useState(''),
        [loadError, setLoadError] = useState('');
    const [saving, setSaving] = useState(false),
        [uploads, setUploads] = useState(0),
        [revision, setRevision] = useState(0);
    const [conflict, setConflict] = useState(false);
    useEffect(() => {
        const controller = new AbortController();
        void (async () => {
            setLoading(true);
            setLoadError('');
            try {
                const detail =
                    id === null
                        ? emptyPresetEditor()
                        : await client.detail(id, controller.signal);
                if (controller.signal.aborted) return;
                if (id !== null && detail.id !== id)
                    throw new Error(
                        'Сервер вернул другой товар. Повторите загрузку.',
                    );
                setEditor({ ...detail, tagsText: detail.tags.join(', ') });
                setConflict(false);
                setError('');
            } catch (reason) {
                if (!controller.signal.aborted)
                    setLoadError(
                        reason instanceof Error
                            ? reason.message
                            : 'Не удалось открыть товар.',
                    );
            } finally {
                if (!controller.signal.aborted) setLoading(false);
            }
        })();
        return () => controller.abort();
    }, [client, id, revision]);
    const modelId = editor?.garment_model_id ?? null;
    const sizeIds = [
        ...new Set(
            editor?.variants.flatMap((row) =>
                row.garment_size_id === null ? [] : [row.garment_size_id],
            ) ?? [],
        ),
    ]
        .sort((a, b) => a - b)
        .join(',');
    const [referenceRevision, setReferenceRevision] = useState(0);
    const [modelState, setModelState] = useState<{
        id: number | null;
        sizesKey: string;
        revision: number;
        value: EditorModel | undefined;
        error: string;
    }>({ id: null, sizesKey: '', revision: -1, value: undefined, error: '' });
    useEffect(() => {
        if (modelId === null) return;
        const controller = new AbortController();
        void client
            .model(
                modelId,
                controller.signal,
                sizeIds ? sizeIds.split(',').map(Number) : [],
            )
            .then((value) => {
                if (value.id !== modelId)
                    throw new Error('Сервер вернул другую модель.');
                if (!controller.signal.aborted)
                    setModelState({
                        id: modelId,
                        sizesKey: sizeIds,
                        revision: referenceRevision,
                        value,
                        error: '',
                    });
            })
            .catch((reason) => {
                if (!controller.signal.aborted)
                    setModelState({
                        id: modelId,
                        sizesKey: sizeIds,
                        revision: referenceRevision,
                        value: undefined,
                        error:
                            reason instanceof Error
                                ? reason.message
                                : 'Не удалось открыть модель.',
                    });
            });
        return () => controller.abort();
    }, [client, modelId, sizeIds, referenceRevision]);
    const fabricIds = [
        ...new Set(
            editor?.variants.flatMap((variant) =>
                variant.fabric_id === null ? [] : [variant.fabric_id],
            ) ?? [],
        ),
    ]
        .sort((a, b) => a - b)
        .join(',');
    const [fabricState, setFabricState] = useState<{
        key: string;
        revision: number;
        values: EditorFabric[];
        error: string;
    }>({ key: '', revision: -1, values: [], error: '' });
    useEffect(() => {
        if (!fabricIds) return;
        const controller = new AbortController();
        void client
            .selectedFabrics(
                fabricIds.split(',').map(Number),
                controller.signal,
            )
            .then((values) => {
                const ids = new Set(values.map((value) => value.id));
                if (fabricIds.split(',').some((id) => !ids.has(Number(id))))
                    throw new Error(
                        'Сервер вернул не все выбранные ткани. Повторите загрузку.',
                    );
                if (!controller.signal.aborted)
                    setFabricState({
                        key: fabricIds,
                        revision: referenceRevision,
                        values,
                        error: '',
                    });
            })
            .catch((reason) => {
                if (!controller.signal.aborted)
                    setFabricState({
                        key: fabricIds,
                        revision: referenceRevision,
                        values: [],
                        error:
                            reason instanceof Error
                                ? reason.message
                                : 'Не удалось открыть ткани.',
                    });
            });
        return () => controller.abort();
    }, [client, fabricIds, referenceRevision]);
    const modelCurrent =
        modelState.id === modelId &&
        modelState.sizesKey === sizeIds &&
        modelState.revision === referenceRevision;
    const fabricsCurrent =
        fabricState.key === fabricIds &&
        fabricState.revision === referenceRevision;
    const model = modelCurrent ? modelState.value : undefined;
    const referenceError =
        (modelId !== null && modelCurrent ? modelState.error : '') ||
        (fabricIds && fabricsCurrent ? fabricState.error : '');
    const referencesLoading =
        (modelId !== null && !model && !referenceError) ||
        Boolean(fabricIds && !fabricsCurrent && !referenceError);
    const submit = async (event: FormEvent) => {
        event.preventDefault();
        if (
            !editor ||
            operation.current ||
            loading ||
            loadError ||
            conflict ||
            referencesLoading ||
            referenceError
        )
            return;
        operation.current = 'save';
        setSaving(true);
        setError('');
        let confirmed = false;
        try {
            await client.save(editor.id, buildPresetPayload(editor));
            confirmed = true;
            operation.current = 'confirmed';
        } catch (reason) {
            if (!alive.current) return;
            if (
                reason instanceof ApiError &&
                reason.code === 'catalog_product_version_conflict'
            )
                setConflict(true);
            if (!(
                reason instanceof DOMException && reason.name === 'AbortError'
            ))
                setError(
                    reason instanceof Error
                        ? reason.message
                        : 'Не удалось сохранить товар.',
                );
        } finally {
            if (!confirmed) operation.current = null;
            if (alive.current) setSaving(false);
        }
        if (confirmed && alive.current) onSaved();
    };
    const upload = async (files: File[]) => {
        if (operation.current || loading || !editor)
            throw new Error('Дождитесь завершения текущей операции.');
        operation.current = 'upload';
        setUploads(1);
        try {
            const urls: string[] = [];
            for (const file of files) {
                const url = await client.upload(file);
                if (!alive.current)
                    throw new DOMException('Редактор закрыт', 'AbortError');
                urls.push(url);
            }
            return urls;
        } finally {
            operation.current = null;
            if (alive.current) setUploads(0);
        }
    };
    return {
        editor,
        setEditor,
        loading,
        loadError,
        error,
        conflict,
        saving,
        uploading: uploads > 0,
        submit,
        upload,
        canClose: () => !operation.current,
        retry: () => {
            if (!operation.current) {
                setLoading(true);
                setLoadError('');
                setRevision((value) => value + 1);
            }
        },
        returnToDraft: () => setLoadError(''),
        retryReferences: () => setReferenceRevision((value) => value + 1),
        model,
        selectedFabrics: fabricIds && fabricsCurrent ? fabricState.values : [],
        referencesLoading,
        referenceError,
    };
}
