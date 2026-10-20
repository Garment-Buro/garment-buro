import { useEffect } from 'react';
import { PiArrowRight, PiCaretDown, PiCheck } from 'react-icons/pi';
import { useModelEditor } from '@/hooks/production/useModelEditor';
import { AssortmentDialog } from './AssortmentDialog';
import { ModelIdentityFields } from './ModelIdentityFields';
import { ModelSizesEditor } from './ModelSizesEditor';
import styles from '../ProductionAdmin.module.css';
export function ModelEditorDialog({
    id,
    onSaved,
    onClose,
    onBusyChange,
}: {
    id: number | null;
    onSaved: () => void;
    onClose: () => void;
    onBusyChange: (busy: boolean) => void;
}) {
    const state = useModelEditor(id, onSaved, onClose);
    const {
        editor,
        setEditor,
        busy,
        saving,
        uploading,
        uploadStatus,
        setUploadStatus,
        submit,
        upload,
        formError,
    } = state;
    useEffect(() => {
        onBusyChange(busy);
    }, [busy, onBusyChange]);
    useEffect(() => () => onBusyChange(false), [onBusyChange]);
    if (state.loading || state.loadError || !editor)
        return (
            <AssortmentDialog
                title={id === null ? 'Новая модель' : 'Изменить модель'}
                onClose={state.close}
            >
                {state.loadError ? (
                    <div role="alert">
                        <p>{state.loadError}</p>
                        <button type="button" onClick={state.retry}>
                            Повторить загрузку модели
                        </button>
                        {editor && (
                            <button type="button" onClick={state.returnToDraft}>
                                Вернуться к черновику
                            </button>
                        )}
                    </div>
                ) : (
                    <p role="status">Загружаем полную модель…</p>
                )}
            </AssortmentDialog>
        );
    return (
        <AssortmentDialog
            title={editor.id ? 'Изменить модель' : 'Новая модель'}
            headerActions={
                <fieldset className={styles.adminFields} disabled={busy}>
                    <details className={styles.patternStatusMenu}>
                        <summary>
                            <span
                                className={styles.patternStatusDot}
                                data-active={editor.is_active}
                            />
                            {editor.is_active ? 'Активна' : 'Скрыта'}
                            <PiCaretDown aria-hidden />
                        </summary>
                        <div role="menu">
                            {(
                                [
                                    [true, 'Активна'],
                                    [false, 'Скрыта'],
                                ] as const
                            ).map(([active, label]) => (
                                <button
                                    type="button"
                                    role="menuitemradio"
                                    aria-checked={editor.is_active === active}
                                    key={String(active)}
                                    onClick={(event) => {
                                        setEditor({
                                            ...editor,
                                            is_active: active,
                                        });
                                        event.currentTarget
                                            .closest('details')
                                            ?.removeAttribute('open');
                                    }}
                                >
                                    <span>{label}</span>
                                    {editor.is_active === active && (
                                        <PiCheck aria-hidden />
                                    )}
                                </button>
                            ))}
                        </div>
                    </details>
                </fieldset>
            }
            description={
                <span className={styles.modelSetupFlow}>
                    <span>1. Модель</span>
                    <PiArrowRight aria-hidden />
                    <span>2. Размеры</span>
                    <PiArrowRight aria-hidden />
                    <span>3. Диапазоны</span>
                </span>
            }
            onClose={state.close}
            closeDisabled={busy}
        >
            <form onSubmit={submit}>
                <fieldset className={styles.adminFields} disabled={busy}>
                    <ModelIdentityFields
                        {...{
                            editor,
                            setEditor,
                            uploading,
                            uploadStatus,
                            setUploadStatus,
                            upload,
                        }}
                    />
                    <ModelSizesEditor
                        key={editor.version ?? 'new'}
                        {...{ editor, setEditor }}
                    />
                    {formError && (
                        <p className={styles.error} role="alert">
                            {formError}
                        </p>
                    )}
                    {state.conflict && (
                        <button type="button" onClick={state.retry}>
                            Перечитать модель и заменить черновик
                        </button>
                    )}
                    <div className={styles.editorActions}>
                        <button type="button" onClick={state.close}>
                            Отмена
                        </button>
                        <button
                            className={styles.primaryButton}
                            disabled={busy || state.conflict}
                        >
                            {saving ? 'Сохраняем…' : 'Сохранить модель'}
                        </button>
                    </div>
                </fieldset>
            </form>
        </AssortmentDialog>
    );
}
