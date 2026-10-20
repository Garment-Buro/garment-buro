'use client';

import { useId, useState } from 'react';
import { useReferenceChoices } from '@/hooks/production/useReferenceDirectory';
import {
    type ReferenceChoice,
    type ReferenceKind,
} from '@/lib/production/referenceDirectory';
import { useSelectedReference } from '@/hooks/production/useSelectedReference';
import styles from '../ProductionAdmin.module.css';

/** A single selected ID is independent of the current result page/search. */
const wording: Record<
    ReferenceKind,
    { label: string; prompt: string; search: string; more: string }
> = {
    'model-categories': {label:'Категория',prompt:'Выберите категорию',search:'Поиск категории модели',more:'Ещё категории моделей'},
    'product-categories': {label:'Категория',prompt:'Выберите категорию',search:'Поиск категории пресета',more:'Ещё категории пресетов'},
    models: {
        label: 'Модель',
        prompt: 'Выберите модель',
        search: 'Поиск модели для расхода',
        more: 'Ещё модели для расхода',
    },
    fabrics: {
        label: 'Ткань',
        prompt: 'Выберите ткань',
        search: 'Поиск ткани для расхода',
        more: 'Ещё ткани для расхода',
    },
    accessories: {
        label: 'Фурнитура',
        prompt: 'Выберите фурнитуру',
        search: 'Поиск фурнитуры для расхода',
        more: 'Ещё фурнитура для расхода',
    },
    boxes: {
        label: 'Коробка',
        prompt: 'Выберите коробку',
        search: 'Поиск коробки',
        more: 'Ещё коробки для правила',
    },
    'accessory-categories': {
        label: 'Категория',
        prompt: 'Выберите категорию',
        search: 'Поиск категории фурнитуры',
        more: 'Ещё категории фурнитуры',
    },
    'tech-card-models': {
        label: 'Модель',
        prompt: 'Выберите модель без техкарты',
        search: 'Поиск модели без техкарты',
        more: 'Ещё модели без техкарты',
    },
    'pattern-sizes': {
        label: 'Размер',
        prompt: 'Выберите размер',
        search: 'Найти размер лекала',
        more: 'Ещё размеры лекала',
    },
};
export function ReferencePicker({
    kind,
    value,
    onChange,
    modelId,
    searchLabel,
    moreLabel,
    required = true,
    emptyLabel,
    activeOnly = false,
}: {
    kind: ReferenceKind;
    value: number;
    onChange: (id: number, row?: ReferenceChoice) => void;
    modelId?: number;
    searchLabel?: string;
    moreLabel?: string;
    required?: boolean;
    emptyLabel?: string;
    activeOnly?: boolean;
}) {
    const [query, setQuery] = useState('');
    const page = useReferenceChoices(kind, {
        query,
        limit: 24,
        ...(activeOnly ? { active: true } : {}),
        ...(kind === 'pattern-sizes' ? { model_id: modelId } : {}),
    });
    const current = useSelectedReference(kind, value);
    const inputId = useId();
    const text = wording[kind];
    return (
        <div>
            <label htmlFor={inputId}>{text.label}</label>
            <select
                id={inputId}
                required={required}
                value={value || ''}
                onChange={(event) => {
                    const id = Number(event.target.value);
                    onChange(
                        id,
                        page.items.find((row) => row.id === id) ??
                            (current?.row?.id === id ? current.row : undefined),
                    );
                }}
            >
                <option value="">{emptyLabel ?? text.prompt}</option>
                {value && !page.items.some((row) => row.id === value) && (
                    <option value={value}>
                        {current?.row?.name ?? `Выбрано №${value}`}
                        {current?.row?.is_active === false ? ' · скрыта' : ''}
                    </option>
                )}
                {page.items.map((row) => (
                    <option key={row.id} value={row.id}>
                        {row.name}
                        {row.max_items ? ` · до ${row.max_items} шт.` : ''}
                        {row.is_active ? '' : ' · скрыта'}
                    </option>
                ))}
            </select>
            <label>
                {searchLabel ?? text.search}
                <input
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                />
            </label>
            {activeOnly && current?.row?.is_active === false && <p role="alert">Выбранная категория скрыта. Восстановите её активность или выберите другую перед сохранением.</p>}
            {current?.error && (
                <p role="alert">
                    {current.error}{' '}
                    <button
                        type="button"
                        onClick={current.retry}
                    >
                        Повторить выбранную запись
                    </button>
                </p>
            )}
            {page.loading && <p role="status">Загружаем варианты…</p>}
            {!page.loading && !page.message && page.items.length === 0 && (
                <p role="status">
                    {query.trim()
                        ? 'По этому запросу ничего не найдено.'
                        : 'В справочнике пока нет записей.'}
                    {value ? ' Выбранная запись сохранена.' : ''}
                </p>
            )}
            {page.message && (
                <p role="alert">
                    {page.message}{' '}
                    <button type="button" onClick={() => void page.retry()}>
                        Повторить поиск
                    </button>
                </p>
            )}
            {page.hasMore && (
                <button
                    type="button"
                    className={styles.secondaryButton}
                    disabled={page.loadingMore}
                    onClick={() => void page.loadMore()}
                >
                    {moreLabel ?? text.more}
                </button>
            )}
        </div>
    );
}
