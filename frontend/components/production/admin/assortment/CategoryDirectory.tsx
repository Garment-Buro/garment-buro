'use client';
import { useState } from 'react';
import { useSelectedReference } from '@/hooks/production/useSelectedReference';
import { PiPencilSimple, PiTShirt } from 'react-icons/pi';
import { useCategoryDirectory } from '@/hooks/production/useReferenceDirectory';
import type { CategoryKind } from '@/lib/production/categoryDirectory';
import { AssortmentFeedback } from './AssortmentDialog';
import { ReferencePicker } from './ReferencePicker';
import styles from '../ProductionAdmin.module.css';
export function CategoryDirectory({ kind, onEdit, onSelect, selectedId, revision = 0, enabled = true }: {
    kind: CategoryKind;
    onEdit: (id: number) => void;
    onSelect?: (id: number, name: string) => void;
    selectedId?: number | null;
    revision?: number;
    enabled?: boolean;
}) {
    const [query, setQuery] = useState(''), [active, setActive] = useState('');
    const page = useCategoryDirectory(kind, { query, active: active ? active === 'true' : undefined, sort: 'name:asc', limit: 24 }, enabled, revision);
    const model = kind === 'model-categories';
    return <section aria-label={model ? 'Категории моделей' : 'Категории пресетов'}>
        <div className={styles.assortmentFilters}>
            <label>Поиск категории<input type="search" value={query} onChange={e => setQuery(e.target.value)}/></label>
            <label>Видимость категории<select value={active} onChange={e => setActive(e.target.value)}><option value="">Все категории</option><option value="true">Активные</option><option value="false">Скрытые</option></select></label>
        </div>
        <AssortmentFeedback loading={page.loading} error={page.message} empty={!page.loading && !page.items.length}/>
        <div className={styles.assortmentCategoryGrid}>
            {page.items.map(category => <article key={category.id} data-category={category.id} data-selected={selectedId === category.id} data-active={category.is_active}>
                <button type="button" className={styles.assortmentCategorySelect} aria-pressed={onSelect ? selectedId === category.id : undefined} onClick={() => onSelect ? onSelect(category.id, category.name) : onEdit(category.id)}>
                    <PiTShirt aria-hidden/><span><strong>{category.name}</strong><small>{category.item_count} {model ? 'моделей' : 'товаров'} · {category.is_active ? 'активна' : 'скрыта'}</small></span>
                </button>
                <button type="button" className={styles.iconButton} aria-label={`Изменить категорию ${category.name}`} onClick={() => onEdit(category.id)}><PiPencilSimple aria-hidden/></button>
            </article>)}
        </div>
        {page.message && <button type="button" onClick={() => void page.retry()}>Повторить список категорий</button>}
        {page.hasMore && <button type="button" disabled={page.loadingMore} onClick={() => void page.loadMore()}>Ещё категории {model ? 'моделей' : 'пресетов'}</button>}
    </section>;
}
export function CategoryFilter({ kind, value, label, onChange, revision = 0 }: {
    kind: CategoryKind;
    value: number;
    label?: string;
    revision?: number;
    onChange: (id: number, name: string) => void;
}) {
    const [open, setOpen] = useState(false);
    const selected = useSelectedReference(kind, value, revision);
    return <div>
        <button type="button" onClick={() => setOpen(current => !current)}>{value ? `Категория: ${selected.row?.name ?? label ?? 'выбрана'}` : 'Выбрать категорию'}</button>
        {open && <ReferencePicker kind={kind} value={value} required={false} emptyLabel="Все категории" onChange={(id, row) => { onChange(id, row?.name ?? ''); setOpen(false); }}/>}
        {selected.error && <p role="alert">{selected.error} <button type="button" onClick={selected.retry}>Повторить выбранную категорию</button></p>}
        {value > 0 && <button type="button" onClick={() => { onChange(0, ''); setOpen(false); }}>Все категории</button>}
    </div>;
}
