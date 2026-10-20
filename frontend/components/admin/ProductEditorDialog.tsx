'use client';
import { useCatalogProductEditor } from '@/hooks/admin/useCatalogProductEditor';
import { productionEditorClient } from '@/hooks/admin/catalogEditorClients';
import { AssortmentDialog } from '@/components/production/admin/assortment/AssortmentDialog';
import { PresetIdentityFields } from './PresetIdentityFields';
import { PresetMediaFields } from './PresetMediaFields';
import { PresetVariantFields } from './PresetVariantFields';
import styles from '@/components/production/admin/ProductionAdmin.module.css';

export function ProductEditorDialog({
    id,
    onClose,
    onSaved,
}: {
    id: number | null;
    onClose: () => void;
    onSaved: () => void;
}) {
    const client = productionEditorClient;
    const state = useCatalogProductEditor(client, id, onSaved);
    const { editor, setEditor, model } = state;
    const busy = state.saving || state.uploading;
    return (
        <AssortmentDialog
            title={id === null ? 'Новый пресет' : 'Изменить пресет'}
            onClose={() => {
                if (state.canClose()) onClose();
            }}
            closeDisabled={busy}
            description="Модель, варианты, изображения и цена товара."
        >
            {state.loading ? (
                <p role="status">Загрузка товара…</p>
            ) : state.loadError ? (
                <div>
                    <p role="alert">{state.loadError}</p>
                    <button type="button" onClick={state.retry}>
                        Повторить
                    </button>
                    {editor && (
                        <button type="button" onClick={state.returnToDraft}>
                            Вернуться к черновику
                        </button>
                    )}
                </div>
            ) : (
                editor && (
                    <form onSubmit={state.submit}>
                        <PresetIdentityFields
                            editor={editor}
                            setEditor={setEditor}
                            disabled={busy}
                            model={model}
                            requiredModel={id === null}
                        />
                        <PresetMediaFields
                            editor={editor}
                            setEditor={setEditor}
                            disabled={busy}
                            upload={state.upload}
                        />
                        <PresetVariantFields
                            editor={editor}
                            setEditor={setEditor}
                            disabled={busy}
                            model={model}
                            selectedFabrics={state.selectedFabrics}
                            referencesLoading={state.referencesLoading}
                            referenceError={state.referenceError}
                            upload={state.upload}
                        />
                        {state.referencesLoading && (
                            <p role="status">Проверка модели и тканей…</p>
                        )}
                        {state.referenceError && (
                            <p role="alert">
                                {state.referenceError}
                                <button
                                    type="button"
                                    onClick={state.retryReferences}
                                >
                                    Повторить загрузку вариантов
                                </button>
                            </p>
                        )}
                        {state.error && <p role="alert">{state.error}</p>}
                        {state.conflict && (
                            <details>
                                <summary>Открыть актуальную версию</summary>
                                <p>
                                    Ваши правки пока остаются в форме.
                                    Скопируйте нужные изменения: загрузка
                                    актуальной версии заменит этот черновик.
                                </p>
                                <button
                                    type="button"
                                    onClick={state.retry}
                                    disabled={busy}
                                >
                                    Заменить черновик актуальной версией
                                </button>
                            </details>
                        )}
                        <div className={styles.editorActions}>
                            <button
                                type="button"
                                disabled={busy}
                                onClick={() => {
                                    if (state.canClose()) onClose();
                                }}
                            >
                                Отмена
                            </button>
                            <button
                                className={styles.primaryButton}
                                disabled={
                                    busy ||
                                    state.conflict ||
                                    state.referencesLoading ||
                                    Boolean(state.referenceError)
                                }
                            >
                                {state.saving
                                    ? 'Сохраняем…'
                                    : 'Сохранить пресет'}
                            </button>
                        </div>
                    </form>
                )
            )}
        </AssortmentDialog>
    );
}
