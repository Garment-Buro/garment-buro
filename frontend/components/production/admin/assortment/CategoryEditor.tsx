'use client';
import { useRef, useState, type FormEvent } from 'react';
import { saveAssortment } from '@/lib/api/productionAssortment';
import { ApiError } from '@/lib/api/http';
import { useAssortmentResource } from '@/hooks/production/useAssortmentResource';
import type { GarmentModelCategory, ProductCategory } from '@/lib/production/assortmentTypes';
import { readModelCategory, readProductCategory, type CategoryKind } from '@/lib/production/categoryDirectory';
import { categorySlug } from '@/lib/production/categoryEditor';
import { AssortmentDialog } from './AssortmentDialog';
import styles from '../ProductionAdmin.module.css';
type Base = {
    id?: number;
    version?: number;
    name: string;
    is_active: boolean;
};
type ModelDraft = Base & {
    kind: 'model-categories';
};
type ProductDraft = Base & {
    kind: 'product-categories';
    slug: string;
    description: string | null;
};
type Draft = ModelDraft | ProductDraft;
type Actions = {
    onClose: () => void;
    onSaved: () => void;
    onBusyChange: (busy: boolean) => void;
};
export function CategoryEditor({ kind, id, ...actions }: Actions & {
    kind: CategoryKind;
    id: number | null;
}) {
    const source = useAssortmentResource<GarmentModelCategory | ProductCategory>(`${kind}/${id}`, id !== null, kind === 'model-categories' ? readModelCategory : readProductCategory);
    if (id !== null && (source.loading || source.error || !source.data || source.data.id !== id))
        return <AssortmentDialog title="Изменить категорию" onClose={actions.onClose}>
            {source.loading ? <p role="status">Загружаем категорию…</p> : <p role="alert">{source.error || 'Не удалось прочитать выбранную категорию.'} <button type="button" onClick={source.reload}>Повторить загрузку категории</button></p>}
        </AssortmentDialog>;
    const initial: Draft = kind === 'model-categories'
        ? { name: '', is_active: true, ...source.data, kind }
        : { name: '', slug: '', description: null, is_active: true, ...source.data, kind };
    return <CategoryForm initial={initial} onReload={source.reload} {...actions}/>;
}
function CategoryForm({ initial, onClose, onSaved, onBusyChange, onReload }: Actions & {
    initial: Draft;
    onReload: () => void;
}) {
    const [draft, setDraft] = useState(initial), [busy, setBusy] = useState(false), [error, setError] = useState('');
    const lock = useRef(false);
    const [conflict, setConflict] = useState(false);
    const submit = async (event: FormEvent) => {
        event.preventDefault();
        if (lock.current)
            return;
        const common = { name: draft.name, is_active: draft.is_active, ...(draft.id ? { expected_version: draft.version } : {}) };
        const payload = draft.kind === 'product-categories'
            ? { ...common, slug: categorySlug(draft.slug || draft.name), description: draft.description } : common;
        if ('slug' in payload && !payload.slug) {
            setError('Укажите адрес категории.');
            return;
        }
        lock.current = true;
        setBusy(true);
        onBusyChange(true);
        setError('');
        setConflict(false);
        try {
            await saveAssortment(draft.id ? `${draft.kind}/${draft.id}` : draft.kind, draft.id ? 'PUT' : 'POST', payload);
        }
        catch (reason) {
            setConflict(reason instanceof ApiError && reason.status === 409);
            setError(reason instanceof Error ? reason.message : 'Не удалось сохранить категорию.');
            return;
        }
        finally {
            lock.current = false;
            setBusy(false);
            onBusyChange(false);
        }
        onSaved();
    };
    return <AssortmentDialog title={draft.id ? 'Изменить категорию' : draft.kind === 'model-categories' ? 'Новая категория моделей' : 'Новая категория'} onClose={() => { if (!lock.current)
        onClose(); }}>
        <form onSubmit={submit}>
            <fieldset className={styles.adminFields} disabled={busy}>
                {draft.kind === 'model-categories'
            ? <ModelCategoryFields value={draft} onChange={setDraft}/>
            : <ProductCategoryFields value={draft} onChange={setDraft}/>}
                {error && <p className={styles.error} role="alert">{error}</p>}
                {conflict && draft.id && <p>Черновик остался на экране. <button type="button" onClick={onReload}>Загрузить актуальную категорию и заменить ввод</button></p>}
                <div className={styles.editorActions}>
                    <button type="button" onClick={onClose}>Отмена</button>
                    <button className={styles.primaryButton}>{busy ? 'Сохраняем…' : 'Сохранить категорию'}</button>
                </div>
            </fieldset>
        </form>
    </AssortmentDialog>;
}
function ModelCategoryFields({ value, onChange }: {
    value: ModelDraft;
    onChange: (value: ModelDraft) => void;
}) {
    return <div className={styles.formGrid}>
        <label>Название<input required maxLength={120} value={value.name} onChange={e => onChange({ ...value, name: e.target.value })}/></label>
        <label className={styles.checkField}><input type="checkbox" checked={value.is_active} onChange={e => onChange({ ...value, is_active: e.target.checked })}/>Категория активна</label>
    </div>;
}
function ProductCategoryFields({ value, onChange }: {
    value: ProductDraft;
    onChange: (value: ProductDraft) => void;
}) {
    return <div className={styles.formGrid}>
        <label>Название<input required maxLength={255} value={value.name} onChange={e => onChange({ ...value, name: e.target.value, ...(!value.id ? { slug: categorySlug(e.target.value) } : {}) })}/></label>
        <label>Адрес категории<input required maxLength={96} pattern="[a-z0-9][a-z0-9-]*" value={value.slug} onChange={e => onChange({ ...value, slug: categorySlug(e.target.value) })}/></label>
        <label className={styles.fullField}>Описание<textarea aria-label="Описание" value={value.description ?? ''} onChange={e => onChange({ ...value, description: e.target.value || null })}/></label>
        <label className={styles.checkField}><input type="checkbox" checked={value.is_active} onChange={e => onChange({ ...value, is_active: e.target.checked })}/>Категория активна</label>
    </div>;
}
