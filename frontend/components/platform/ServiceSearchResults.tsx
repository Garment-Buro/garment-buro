'use client';

import dynamic from 'next/dynamic';
import { useState } from 'react';
import { useFavoriteMembership } from '@/hooks/catalog/useFavoriteMembership';
import { useSavedProducts } from '@/hooks/catalog/useSavedProducts';
import { useStorefrontProducts } from '@/hooks/catalog/useStorefrontProducts';
import { productConstructorHref, type StorefrontProduct } from '@/lib/api/storefront';
import type {StorefrontInitial} from '@/lib/catalog/storefront';
import { ServiceCatalogIcon as Icon } from './ServiceCatalogIcon';
import { ServiceFavoritesSheet } from './ServiceFavoritesSheet';
import { ServiceFiltersSheet } from './ServiceFiltersSheet';
import { ServiceProductGrid } from './ServiceProductGrid';
import { createCatalogQuery, defaultFilters, hasActiveFilters, type CatalogFilters } from './serviceCatalog';
import styles from './ServiceSearchResults.module.css';

const AuthPopup = dynamic(() => import('@/components/auth/AuthPopup').then(module => module.AuthPopup));

export function ServiceSearchResults({ query, onBack, initialProducts }: { query: string; onBack: () => void; initialProducts?: StorefrontInitial }) {
    const [favoritesOpen, setFavoritesOpen] = useState(false);
    const [filtersOpen, setFiltersOpen] = useState(false);
    const [authOpen, setAuthOpen] = useState(false);
    const [filters, setFilters] = useState<CatalogFilters>(defaultFilters);
    const [expandedId, setExpandedId] = useState<number | null>(null);
    const [announcement, setAnnouncement] = useState('');
    const catalog = useStorefrontProducts(createCatalogQuery(query, filters), true, initialProducts);
    const saved = useSavedProducts(favoritesOpen);
    const membership = useFavoriteMembership([...catalog.items, ...saved.items].map(product => product.id));
    const toggleExpanded = (id: number) => setExpandedId(previous => previous === id ? null : id);
    const openAuth = () => { setFavoritesOpen(false); setExpandedId(null); setAuthOpen(true); };
    const toggleFavorite = async (id: number) => {
        if(!membership.authenticated) {openAuth(); return}
        if(await membership.toggle(id) && favoritesOpen) void saved.retry();
    };
    const share = async (product: StorefrontProduct) => {
        const url = new URL(productConstructorHref(product.id), window.location.origin).href;
        try {
            // Preserve transient user activation on iOS.
            if (typeof navigator.share === 'function') await navigator.share({title:product.title, text:product.title, url});
            else {await navigator.clipboard.writeText(url); setAnnouncement('Ссылка скопирована')}
        } catch (error) {
            if (!(error instanceof DOMException && error.name === 'AbortError')) setAnnouncement('Не удалось поделиться ссылкой');
        }
    };
    const gridActions = {favorites:membership.ids, knownIds:membership.knownIds, pendingIds:membership.pendingIds,
        authenticated:membership.authenticated, sessionReady:membership.sessionReady, onFavorite:(id:number) => {void toggleFavorite(id)},
        onShare:(product:StorefrontProduct) => {void share(product)}, onToggleExpanded:toggleExpanded};

    return <>
        <section className={styles.results} aria-labelledby="search-clothing-title">
            <div className={styles.toolbar}>
                <button type="button" onClick={onBack} aria-label="Вернуться на главную"><Icon name="back" width={15} height={13} /></button>
                <h2 id="search-clothing-title">ОДЕЖДА</h2>
                <button type="button" className={styles.sort} aria-label="Открыть фильтры" aria-haspopup="dialog" aria-expanded={filtersOpen} data-active={hasActiveFilters(filters)} onClick={() => setFiltersOpen(true)}>
                    <Icon name="sort-up" width={8.57895} height={11.7368} />
                    <span className={styles.sortDown}><Icon name="sort-down" width={8.57895} height={11.7368} /></span>
                </button>
                <button type="button" aria-label="Открыть избранное" aria-haspopup="dialog" aria-expanded={favoritesOpen} disabled={!membership.sessionReady} onClick={() => {
                    setExpandedId(null);
                    if(membership.authenticated) setFavoritesOpen(true);
                    else openAuth();
                }}><Icon name="favorites" width={12} height={12} /></button>
            </div>
            {membership.error != null && <p className={styles.favoriteError} role="alert">Не удалось обновить избранное. <button type="button" onClick={() => {void membership.retry()}}>Повторить проверку</button></p>}
            <ServiceProductGrid {...gridActions} items={catalog.items} status={catalog.status} error={catalog.error} loadingMore={catalog.loadingMore} label="Результаты поиска одежды" expandedId={favoritesOpen ? null : expandedId}
                hasMore={catalog.nextCursor !== null} onLoadMore={() => {void catalog.loadMore()}} onRetry={() => {void catalog.retry()}} />
        </section>
        {filtersOpen && <ServiceFiltersSheet value={filters} onClose={() => setFiltersOpen(false)} onApply={next => { setFilters(next); setFiltersOpen(false); setExpandedId(null); }} />}
        {favoritesOpen && <ServiceFavoritesSheet count={saved.authenticated ? saved.items.length : 0} hasMore={saved.authenticated && saved.nextCursor !== null} countLabel="Загружено товаров из избранного" onClose={() => { setExpandedId(null); setFavoritesOpen(false); }}>
            {saved.authenticated ? <ServiceProductGrid {...gridActions} items={saved.items} status={saved.status} error={saved.error} loadingMore={saved.loadingMore} label="Избранные товары" expandedId={expandedId}
                hasMore={saved.nextCursor !== null} onLoadMore={() => {void saved.loadMore()}} onRetry={() => {void saved.retry()}} />
                : <p className={styles.empty}>Войдите, чтобы посмотреть избранное. <button type="button" onClick={openAuth}>Войти</button></p>}
            {membership.error != null && <p className={styles.favoriteError} role="alert">Не удалось обновить избранное. <button type="button" onClick={() => {void membership.retry()}}>Повторить проверку</button></p>}
            <span className="sr-only" role="status">{announcement}</span>
        </ServiceFavoritesSheet>}
        {authOpen && <AuthPopup isOpen onClose={() => setAuthOpen(false)} />}
        <span className="sr-only" role="status">{favoritesOpen ? '' : announcement}</span>
    </>;
}
