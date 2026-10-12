'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useId, useState, useSyncExternalStore } from 'react';

import { useServiceFavoritesStore } from '@/store/serviceFavoritesStore';
import { ServiceCatalogIcon as Icon } from './ServiceCatalogIcon';
import { ServiceFavoritesSheet } from './ServiceFavoritesSheet';
import { ServiceFiltersSheet } from './ServiceFiltersSheet';
import { defaultFilters, filterCatalog, hasActiveFilters, type CatalogFilters } from './serviceCatalog';

import styles from './ServiceSearchResults.module.css';

const ASSETS = '/service-home/search';
const products = [
    { id: 'top', title: 'Майка Horse Com', artwork: 'top', backdrop: 'person-liza', price: 8000, category: 'Майки', color: 'Чёрный', source: 'user', createdOrder: 6 },
    { id: 'shoes', title: 'Кеды OG Run', artwork: 'shoes', backdrop: 'person-man', price: 8000, category: 'Аксессуары', color: 'Чёрный', source: 'community', createdOrder: 5 },
    { id: 'cap', title: 'Кепка RGM+', artwork: 'cap', backdrop: 'person-liza', price: 8000, category: 'Аксессуары', color: 'Серый', source: 'user', createdOrder: 4 },
    { id: 'hoodie', title: 'Худи', artwork: 'hoodie', backdrop: 'person-man', price: 8000, category: 'Худи', color: 'Чёрный', source: 'community', createdOrder: 3 },
    { id: 'top-second', title: 'Майка Horse Com', artwork: 'top', backdrop: 'person-liza', price: 8000, category: 'Майки', color: 'Чёрный', source: 'user', createdOrder: 2 },
    { id: 'top-third', title: 'Майка Horse Com', artwork: 'top', backdrop: 'person-man', price: 8000, category: 'Майки', color: 'Чёрный', source: 'community', createdOrder: 1 },
] as const;

// These are the same preview products as the home artwork, pending catalog integration.
const matchesQuery = (title: string, query: string) => (
    `${title} garment одежда`.toLocaleLowerCase('ru').includes(query.trim().toLocaleLowerCase('ru'))
);

export const hasServiceSearchProducts = (query: string) => products.some(product => matchesQuery(product.title, query));

const subscribeToWidth = (callback: () => void) => {
    const queries = [window.matchMedia('(min-width: 600px)'), window.matchMedia('(min-width: 900px)')];
    queries.forEach(query => query.addEventListener('change', callback));
    return () => queries.forEach(query => query.removeEventListener('change', callback));
};
const getColumnCount = () => window.matchMedia('(min-width: 900px)').matches
    ? 4 : window.matchMedia('(min-width: 600px)').matches ? 3 : 2;
const getServerColumnCount = () => 2;

type Product = typeof products[number];

function ProductGrid({ items, favorites, onFavorite, onShare, label, expandedId, onToggleExpanded }: {
    items: readonly Product[];
    favorites: readonly string[];
    onFavorite: (id: string) => void;
    onShare: (title: string) => void;
    label: string;
    expandedId: string | null;
    onToggleExpanded: (id: string) => void;
}) {
    const columnCount = useSyncExternalStore(subscribeToWidth, getColumnCount, getServerColumnCount);
    const gridId = useId();
    const columns = Array.from({ length: columnCount }, (_, column) => (
        items.filter((_, index) => index % columnCount === column)
    ));

    return <div className={styles.scroller} tabIndex={0} role="group" aria-label={label}>
        {items.length ? <div className={styles.columns}>
            {columns.map((column, index) => <div className={styles.column} key={index} data-search-column={index}>
                {column.map(product => {
                    const isExpanded = expandedId === product.id;
                    const isFavorite = favorites.includes(product.id);
                    const actionsId = `${gridId}-actions-${product.id}`;
                    const favoriteLabel = `${product.title}: ${isFavorite ? 'убрать из избранного' : 'в избранное'}`;
                    return <article key={product.id} className={styles.card} data-expanded={isExpanded} data-search-product={product.id}>
                        <div className={styles.cardBackdrop} aria-hidden="true">
                            <Image src={`${ASSETS}/search-${product.backdrop}.webp`} alt="" width={640} height={product.backdrop === 'person-liza' ? 800 : 773} unoptimized className={product.backdrop === 'person-liza' ? styles.lizaBackdrop : styles.manBackdrop} />
                        </div>
                        <button type="button" className={styles.summary} aria-label={`${product.title}: ${isExpanded ? 'свернуть' : 'раскрыть'} карточку`} aria-expanded={isExpanded} aria-controls={actionsId} onClick={() => onToggleExpanded(product.id)}>
                            <span className={styles.media}>
                                <span className={`${styles.crop} ${styles[product.artwork]}`}>
                                    <Image src={`${ASSETS}/search-${product.artwork}.webp`} alt={product.title} width={640} height={product.artwork === 'hoodie' ? 800 : product.artwork === 'shoes' ? 456 : 640} unoptimized />
                                </span>
                            </span>
                            <span className={styles.meta}><span className={styles.title}>{product.title}</span><span className={styles.price}>{product.price}₽</span></span>
                        </button>
                        {isFavorite && <button type="button" className={styles.cardFavorite} aria-label={favoriteLabel} aria-pressed={isFavorite} onClick={() => onFavorite(product.id)}>
                            <Icon name="card-favorite" width={12} height={12} />
                        </button>}
                        <div id={actionsId} className={styles.actionsReveal} inert={!isExpanded} aria-hidden={!isExpanded}>
                            <div className={styles.actionsClip}><div className={styles.actions}>
                                <button type="button" className={styles.like} aria-label={favoriteLabel} aria-pressed={isFavorite} onClick={() => onFavorite(product.id)}><Icon name="like" width={19} height={19} filled={isFavorite} /></button>
                                <Link href="/constructor" className={styles.add} aria-label={`${product.title}: создать изделие`}><Icon name="plus" width={17} height={17} /></Link>
                                <button type="button" className={styles.share} aria-label={`${product.title}: поделиться`} onClick={() => onShare(product.title)}><Icon name="share" width={17} height={17} /></button>
                            </div></div>
                        </div>
                    </article>;
                })}
            </div>)}
        </div> : <p className={styles.empty} role="status">{label === 'Избранные товары' ? 'В избранном пока пусто. Нажмите на сердечко на карточке товара.' : 'Ничего не найдено'}</p>}
    </div>;
}

export function ServiceSearchResults({ query, onBack }: { query: string; onBack: () => void }) {
    const favorites = useServiceFavoritesStore(state => state.ids);
    const toggleFavorite = useServiceFavoritesStore(state => state.toggle);
    const [favoritesOpen, setFavoritesOpen] = useState(false);
    const [filtersOpen, setFiltersOpen] = useState(false);
    const [filters, setFilters] = useState<CatalogFilters>(defaultFilters);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const toggleExpanded = (id: string) => setExpandedId(previous => previous === id ? null : id);
    const [announcement, setAnnouncement] = useState('');
    const visibleProducts = products.filter(product => matchesQuery(product.title, query));
    const orderedProducts = filterCatalog(visibleProducts, filters);
    const favoriteProducts = products.filter(product => favorites.includes(product.id));

    const share = async (title: string) => {
        try {
            // Call synchronously from the click: iOS requires transient user activation.
            if (typeof navigator.share === 'function') {
                await navigator.share({ title, text: title, url: window.location.href });
            }
            else {
                await navigator.clipboard.writeText(window.location.href);
                setAnnouncement('Ссылка скопирована');
            }
        } catch (error) {
            if (!(error instanceof DOMException && error.name === 'AbortError')) {
                setAnnouncement('Не удалось поделиться ссылкой');
            }
        }
    };

    return <>
        <section className={styles.results} aria-labelledby="search-clothing-title">
            <div className={styles.toolbar}>
                <button type="button" onClick={onBack} aria-label="Вернуться на главную"><Icon name="back" width={15} height={13} /></button>
                <h2 id="search-clothing-title">ОДЕЖДА</h2>
                <button type="button" className={styles.sort} aria-label="Открыть фильтры" aria-haspopup="dialog" aria-expanded={filtersOpen} data-active={hasActiveFilters(filters)} onClick={() => setFiltersOpen(true)}>
                    <Icon name="sort-up" width={8.57895} height={11.7368} />
                    <span className={styles.sortDown}><Icon name="sort-down" width={8.57895} height={11.7368} /></span>
                </button>
                <button type="button" aria-label="Открыть избранное" aria-haspopup="dialog" aria-expanded={favoritesOpen} onClick={() => { setExpandedId(null); setFavoritesOpen(true); }}><Icon name="favorites" width={12} height={12} /></button>
            </div>
            <ProductGrid items={orderedProducts} favorites={favorites} onFavorite={toggleFavorite} onShare={title => void share(title)} label="Результаты поиска одежды" expandedId={favoritesOpen ? null : expandedId} onToggleExpanded={toggleExpanded} />
        </section>
        {filtersOpen && <ServiceFiltersSheet value={filters} onClose={() => setFiltersOpen(false)} onApply={next => { setFilters(next); setFiltersOpen(false); }} />}
        {favoritesOpen && <ServiceFavoritesSheet count={favoriteProducts.length} onClose={() => { setExpandedId(null); setFavoritesOpen(false); }}>
            <ProductGrid items={favoriteProducts} favorites={favorites} onFavorite={toggleFavorite} onShare={title => void share(title)} label="Избранные товары" expandedId={expandedId} onToggleExpanded={toggleExpanded} />
            <span className="sr-only" role="status">{announcement}</span>
        </ServiceFavoritesSheet>}
        <span className="sr-only" role="status">{favoritesOpen ? '' : announcement}</span>
    </>;
}
