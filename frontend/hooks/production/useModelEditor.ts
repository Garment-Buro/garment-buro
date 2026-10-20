import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ApiError } from '@/lib/api/http';
import {
    saveAssortment,
    uploadAssortmentMedia,
} from '@/lib/api/productionAssortment';
import { requestModelDetail } from '@/lib/production/referenceDirectory';
import {
    buildModelPayload,
    emptyModel,
    readModelUpload,
    toModelEditor,
    type ModelEditor,
} from '@/lib/production/modelEditor';
import { useProductionAuthStore } from '@/store/productionAuthStore';
type UploadStatus = {
    state: 'idle' | 'uploading' | 'success' | 'error';
    fileName?: string;
    message?: string;
};
export function useModelEditor(
    id: number | null,
    onSaved: () => void,
    onClose: () => void,
) {
    const [editor, setEditor] = useState<ModelEditor | null>(() =>
        id === null ? emptyModel() : null,
    );
    const [loading, setLoading] = useState(id !== null);
    const [loadError, setLoadError] = useState('');
    const [formError, setFormError] = useState('');
    const [conflict, setConflict] = useState(false);
    const [revision, setRevision] = useState(0);
    const [operation, setOperation] = useState<'save' | 'upload' | null>(null);
    const [uploadStatus, setUploadStatus] = useState<UploadStatus>({
        state: 'idle',
    });
    const lock = useRef<'save' | 'upload' | 'confirmed' | null>(null);
    const alive = useRef(true);
    useEffect(() => {
        alive.current = true;
        return () => {
            alive.current = false;
        };
    }, []);
    useEffect(() => {
        if (id === null) return;
        const controller = new AbortController();
        void (async () => {
            setLoading(true);
            setLoadError('');
            try {
                const model = await useProductionAuthStore
                    .getState()
                    .runAuthenticated(() =>
                        requestModelDetail(id, controller.signal),
                    );
                const next = toModelEditor(model);
                if (controller.signal.aborted) return;
                setEditor(next);
                setConflict(false);
                setFormError('');
                setUploadStatus(
                    next.size_chart_media_object_id
                        ? {
                              state: 'success',
                              message: 'Таблица размеров уже загружена',
                          }
                        : { state: 'idle' },
                );
            } catch (reason) {
                if (!controller.signal.aborted)
                    setLoadError(
                        reason instanceof Error
                            ? reason.message
                            : 'Не удалось загрузить модель.',
                    );
            } finally {
                if (!controller.signal.aborted) setLoading(false);
            }
        })();
        return () => controller.abort();
    }, [id, revision]);
    const submit = async (event: FormEvent) => {
        event.preventDefault();
        if (!editor || loading || loadError || conflict || lock.current) return;
        lock.current = 'save';
        setOperation('save');
        setFormError('');
        let confirmed = false;
        try {
            await saveAssortment(
                editor.id ? `models/${editor.id}` : 'models',
                editor.id ? 'PUT' : 'POST',
                buildModelPayload(editor),
            );
            confirmed = true;
            lock.current = 'confirmed';
        } catch (reason) {
            if (alive.current) {
                if (
                    reason instanceof ApiError &&
                    reason.code === 'crm_reference_version_conflict'
                )
                    setConflict(true);
                setFormError(
                    reason instanceof Error
                        ? reason.message
                        : 'Не удалось сохранить модель.',
                );
            }
        } finally {
            if (!confirmed) lock.current = null;
            if (alive.current) setOperation(null);
        }
        // A rendering/list refresh failure cannot turn a confirmed write into a failed save.
        if (confirmed && alive.current) onSaved();
    };
    const upload = async (file: File) => {
        if (lock.current || loading || !editor) return;
        lock.current = 'upload';
        setOperation('upload');
        setUploadStatus({ state: 'uploading', fileName: file.name });
        setFormError('');
        try {
            const uploaded = readModelUpload(
                await uploadAssortmentMedia(file, 'public'),
            );
            if (!alive.current) return;
            setEditor((current) =>
                current
                    ? {
                          ...current,
                          size_chart_media_object_id: uploaded.id,
                          size_chart_url: uploaded.url,
                      }
                    : current,
            );
            setUploadStatus({ state: 'success', fileName: file.name });
        } catch (reason) {
            if (!alive.current) return;
            const message =
                reason instanceof Error
                    ? reason.message
                    : 'Не удалось загрузить изображение.';
            setFormError(message);
            setUploadStatus({ state: 'error', fileName: file.name, message });
        } finally {
            lock.current = null;
            if (alive.current) setOperation(null);
        }
    };
    return {
        editor,
        setEditor,
        loading,
        loadError,
        formError,
        conflict,
        uploadStatus,
        setUploadStatus,
        saving: operation === 'save',
        uploading: operation === 'upload',
        busy: operation !== null,
        submit,
        upload,
        close: () => {
            if (!lock.current || lock.current === 'confirmed') onClose();
        },
        retry: () => {
            if (!lock.current) {
                setLoading(true);
                setLoadError('');
                setRevision((value) => value + 1);
            }
        },
        returnToDraft: () => setLoadError(''),
    };
}
