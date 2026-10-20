'use client';

import type { ReactNode } from 'react';
import styles from './CollectionProductPicker.module.css';

export type PickerProduct = { id: number; title: string; price: string | number; is_active?: boolean };
type Props = {
    ids: number[];
    disabled: boolean;
    onChange: (ids: number[]) => void;
    query: string;
    setQuery: (query: string) => void;
    known: ReadonlyMap<number, PickerProduct>;
    description: ReactNode;
    unavailableIds?: number[];
    selectionError?: boolean;
    onRetrySelection?: () => unknown;
    catalog: {
        items: PickerProduct[]; loading: boolean; error: string | boolean;
        hasMore: boolean; loadingMore: boolean;
        retry: () => unknown; loadMore: () => unknown;
    };
};

export function CollectionProductPicker({ ids, disabled, onChange, query, setQuery, known,
    description, unavailableIds, selectionError, onRetrySelection, catalog }: Props) {
    const move = (index: number, step: number) => {
        const next = [...ids];
        [next[index], next[index + step]] = [next[index + step], next[index]];
        onChange(next);
    };
    return (
        <fieldset className={styles.collection} disabled={disabled}>
            <legend>Коллекция · {ids.length} из 50 моделей</legend>
            <p>Модели показываются на лендинге в выбранном порядке. {description}</p>
            {ids.length > 0 && (
                <ol className={styles.selected} aria-label="Модели коллекции">
                    {ids.map((id, index) => (
                        <li key={id}>
                            <span>
                                {known.get(id)?.title ?? `Модель №${id}`}
                                {unavailableIds?.includes(id) && (
                                    <small>
                                        Сейчас недоступна в каталоге. Удалите её перед публикацией.
                                    </small>
                                )}
                            </span>
                            <div className={styles.actions}>
                                <button
                                    type="button"
                                    disabled={index === 0}
                                    aria-label={`Поднять модель ${id}`}
                                    onClick={() => move(index, -1)}
                                >
                                    ↑
                                </button>
                                <button
                                    type="button"
                                    disabled={index === ids.length - 1}
                                    aria-label={`Опустить модель ${id}`}
                                    onClick={() => move(index, 1)}
                                >
                                    ↓
                                </button>
                                <button
                                    type="button"
                                    aria-label={`Убрать модель ${id}`}
                                    onClick={() => onChange(ids.filter((value) => value !== id))}
                                >
                                    Убрать
                                </button>
                            </div>
                        </li>
                    ))}
                </ol>
            )}
            {Boolean(selectionError) && (
                <p role="alert">
                    Названия выбранных моделей недоступны. Выбор сохранён.{' '}
                    <button type="button" onClick={() => void onRetrySelection?.()}>
                        Повторить
                    </button>
                </p>
            )}
            <label className={styles.field}>
                Найти модель в каталоге
                <input
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Название модели"
                />
            </label>
            {catalog.loading && <p role="status">Загружаем каталог…</p>}
            {Boolean(catalog.error) && (
                <p role="alert">
                    {typeof catalog.error === 'string' ? catalog.error : 'Каталог недоступен.'}{' '}
                    <button type="button" onClick={() => void catalog.retry()}>
                        Повторить
                    </button>
                </p>
            )}
            <div className={styles.products}>
                {catalog.items.map((item) => {
                    const checked = ids.includes(item.id);
                    return (
                        <label key={item.id} className={styles.product}>
                            <input
                                type="checkbox"
                                checked={checked}
                                disabled={!checked && ids.length >= 50}
                                onChange={() =>
                                    onChange(
                                        checked
                                            ? ids.filter((id) => id !== item.id)
                                            : [...ids, item.id],
                                    )
                                }
                            />
                            <span>
                                <strong>{item.title}</strong>
                                <small>#{item.id} · {Number(item.price).toLocaleString('ru-RU')} ₽{item.is_active === false ? ' · Скрыта' : ''}</small>
                            </span>
                        </label>
                    );
                })}
            </div>
            {!catalog.loading && !catalog.error && !catalog.items.length && <p>Модели не найдены.</p>}
            {catalog.hasMore && (
                <button
                    type="button"
                    disabled={catalog.loadingMore}
                    onClick={() => void catalog.loadMore()}
                >
                    {catalog.loadingMore ? 'Загружаем…' : 'Ещё модели'}
                </button>
            )}
        </fieldset>
    );
}
