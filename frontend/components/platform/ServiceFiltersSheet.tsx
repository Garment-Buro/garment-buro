'use client';

import { useState, type CSSProperties, type FormEvent } from 'react';
import { useStorefrontOptions } from '@/hooks/catalog/useStorefrontOptions';
import { ServiceCatalogSheet } from './ServiceCatalogSheet';
import { defaultFilters, type CatalogFilters, type Sort } from './serviceCatalog';
import styles from './ServiceFiltersSheet.module.css';

const money = (amount: number | null) => amount === null ? '' : `${amount.toLocaleString('ru-RU')} ₽`;
const PRICE_LIMIT = 50000;
const toSlider = (price: number | null) => (Math.min(price ?? PRICE_LIMIT, PRICE_LIMIT) / PRICE_LIMIT) ** (1 / 2.55) * 1000;
const fromSlider = (position: number) => Math.round(PRICE_LIMIT * (position / 1000) ** 2.55 / 100) * 100;
const sorting: { value: Sort; label: string }[] = [
    { value: 'expensive', label: 'Дороже' }, { value: 'cheap', label: 'Дешевле' },
    { value: 'oldest', label: 'Старые' }, { value: 'newest', label: 'Новые' },
];

export function ServiceFiltersSheet({ value, onApply, onClose }: {
    value: CatalogFilters; onApply: (filters: CatalogFilters) => void; onClose: () => void;
}) {
    const [draft, setDraft] = useState(value);
    const [minText, setMinText] = useState(money(value.minPrice));
    const [maxText, setMaxText] = useState(money(value.maxPrice));
    const [error, setError] = useState('');
    const {options, error:optionsError, retry} = useStorefrontOptions();
    const reset = () => {
        setDraft(defaultFilters); setMinText(money(defaultFilters.minPrice)); setMaxText(''); setError('');
    };
    const toggle = <T,>(values: T[], item: T) => values.includes(item) ? values.filter(value => value !== item) : [...values, item];
    const changePrice = (bound: 'minPrice' | 'maxPrice', text: string) => {
        const digits = text.replace(/[^0-9]/g, '').slice(0, 10);
        const price = digits ? Number(digits) : bound === 'minPrice' ? 0 : null;
        if (bound === 'minPrice') setMinText(digits);
        else setMaxText(digits);
        setDraft(previous => ({ ...previous, [bound]: price }));
        setError('');
    };
    const slidePrice = (bound: 'minPrice' | 'maxPrice', position: number) => {
        const amount = fromSlider(position);
        const price = bound === 'minPrice' ? Math.min(amount, draft.maxPrice ?? PRICE_LIMIT)
            : position === 1000 ? null : Math.max(amount, draft.minPrice);
        setDraft(previous => ({ ...previous, [bound]: price }));
        if (bound === 'minPrice') setMinText(money(price));
        else setMaxText(money(price));
        setError('');
    };
    const submit = (event: FormEvent) => {
        event.preventDefault();
        if (draft.maxPrice !== null && draft.minPrice > draft.maxPrice) { setError('Цена «От» должна быть не больше цены «До».'); return; }
        onApply(draft);
    };

    return <ServiceCatalogSheet title="ФИЛЬТРЫ" onClose={onClose} className={styles.sheet}
        headerAction={<button type="button" className={styles.reset} onClick={reset}>Сбросить</button>}>
        <form className={styles.form} onSubmit={submit}>
            <div className={styles.body}>
                {optionsError ? <p className={styles.error} role="alert">Не удалось загрузить категории и цвета. <button type="button" onClick={retry}>Повторить</button></p>
                    : !options && <p role="status">Загружаем категории и цвета…</p>}
                {options && <>
                    <fieldset className={styles.categories}>
                        <legend className="sr-only">Категория одежды</legend>
                        <div className={styles.categoryRow}>{options.categories.map(category => <button key={category.id} type="button" aria-pressed={draft.categories.includes(category.id)}
                            onClick={() => setDraft(previous => ({ ...previous, categories: toggle(previous.categories, category.id) }))}>{category.name}</button>)}</div>
                    </fieldset>
                    <fieldset className={styles.colors}>
                        <legend className={styles.label}>Цвет одежды</legend>
                        <div className={styles.colorButtons}>{options.colors.map(color => <button key={color} type="button" aria-pressed={draft.colors.includes(color)}
                            onClick={() => setDraft(previous => ({ ...previous, colors: toggle(previous.colors, color) }))}>{color}</button>)}</div>
                    </fieldset>
                </>}
                <fieldset className={styles.sources}>
                    <legend className={styles.label}>Автор товара</legend>
                    <div className={styles.sourceRow}>{([{ value: 'garment_buro', label: 'Garment Buro' }, { value: 'user', label: 'От пользователя' }] as const).map(source => <button
                        key={source.value} type="button" aria-pressed={draft.source === source.value}
                        onClick={() => setDraft(previous => ({ ...previous, source: previous.source === source.value ? null : source.value }))}>{source.label}</button>)}</div>
                </fieldset>
                <div className={styles.divider} aria-hidden="true" />
                <fieldset className={styles.sorting}>
                    <legend className="sr-only">Порядок товаров</legend>
                    {sorting.map(option => <button key={option.value} type="button" aria-pressed={draft.sort === option.value}
                        onClick={() => setDraft(previous => ({ ...previous, sort: option.value }))}>{option.label}</button>)}
                </fieldset>
                <fieldset className={styles.price}>
                    <legend className={styles.label}>Цена</legend>
                    <div className={styles.priceFields}>
                        <label>От<input aria-label="Цена от" inputMode="numeric" value={minText} onChange={event => changePrice('minPrice', event.target.value)}
                            onFocus={() => setMinText(String(draft.minPrice))} onBlur={() => setMinText(money(draft.minPrice))} aria-invalid={!!error} aria-describedby={error ? 'catalog-price-error' : undefined} /></label>
                        <label>До<input aria-label="Цена до" inputMode="numeric" placeholder="Без ограничения" value={maxText} onChange={event => changePrice('maxPrice', event.target.value)}
                            onFocus={() => setMaxText(draft.maxPrice === null ? '' : String(draft.maxPrice))} onBlur={() => setMaxText(money(draft.maxPrice))} aria-invalid={!!error} aria-describedby={error ? 'catalog-price-error' : undefined} /></label>
                    </div>
                    <div className={styles.range} style={{ '--range-start': `${toSlider(draft.minPrice) / 10}%`, '--range-end': `${toSlider(draft.maxPrice) / 10}%` } as CSSProperties}>
                        <div className={styles.rangeTrack} aria-hidden="true"><span /></div>
                        <input type="range" min={0} max={1000} step={1} value={toSlider(draft.minPrice)}
                            aria-label="Минимальная цена" aria-valuetext={money(draft.minPrice)} onChange={event => slidePrice('minPrice', Number(event.target.value))} />
                        <input type="range" min={0} max={1000} step={1} value={toSlider(draft.maxPrice)}
                            aria-label="Максимальная цена" aria-valuetext={draft.maxPrice === null ? 'Без ограничения' : money(draft.maxPrice)} onChange={event => slidePrice('maxPrice', Number(event.target.value))} />
                    </div>
                    {error && <p id="catalog-price-error" className={styles.error} role="alert">{error}</p>}
                </fieldset>
            </div>
            <div className={styles.footer}><button type="submit">Показать результаты</button></div>
        </form>
    </ServiceCatalogSheet>;
}
