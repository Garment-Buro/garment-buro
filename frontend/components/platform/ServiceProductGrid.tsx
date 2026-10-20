'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useId } from 'react';
import { productConstructorHref, type StorefrontProduct } from '@/lib/api/storefront';
import { PageCursorExpiredError } from '@/lib/catalog/pagedResource';
import { ServiceCatalogIcon as Icon } from './ServiceCatalogIcon';
import styles from './ServiceSearchResults.module.css';

export function ServiceProductGrid({ items, favorites, knownIds, pendingIds, authenticated, sessionReady, onFavorite, onShare, label,
    expandedId, onToggleExpanded, status, error, loadingMore, hasMore, onLoadMore, onRetry }: {
    items: readonly StorefrontProduct[];
    favorites: readonly number[];
    knownIds: readonly number[];
    pendingIds: readonly number[];
    authenticated: boolean;
    sessionReady: boolean;
    onFavorite: (id: number) => void;
    onShare: (product: StorefrontProduct) => void;
    label: string;
    expandedId: number | null;
    onToggleExpanded: (id: number) => void;
    status: 'idle' | 'loading' | 'ready' | 'error';
    error: unknown;
    loadingMore: boolean;
    hasMore: boolean;
    onLoadMore: () => void;
    onRetry: () => void;
}) {
    const cursorExpired = error instanceof PageCursorExpiredError;
    const gridId = useId();
    return <div className={styles.scroller} tabIndex={0} role="group" aria-label={label} aria-busy={status === 'loading' || loadingMore}>
        {status === 'loading' || status === 'idle' ? <p className={styles.empty} role="status">Загружаем товары…</p>
            : status === 'error' ? <p className={styles.empty} role="alert">Не удалось загрузить товары. <button type="button" onClick={onRetry}>Повторить</button></p>
                : items.length ? <div className={styles.grid} data-search-grid>
                    {items.map(product => {
                        const isExpanded = expandedId === product.id;
                        const isFavorite = favorites.includes(product.id);
                        const pending = pendingIds.includes(product.id);
                        const unknown = !sessionReady || (authenticated && !knownIds.includes(product.id));
                        const actionsId = `${gridId}-actions-${product.id}`;
                        const favoriteLabel = `${product.title}: ${pending ? 'сохраняем избранное' : unknown ? 'проверяем избранное' : isFavorite ? 'убрать из избранного' : 'в избранное'}`;
                        return <article key={product.id} className={styles.card} data-expanded={isExpanded} data-search-product={product.id}>
                            <button type="button" className={styles.summary} aria-label={`${product.title}: ${isExpanded ? 'свернуть' : 'раскрыть'} карточку`} aria-expanded={isExpanded} aria-controls={actionsId} onClick={() => onToggleExpanded(product.id)}>
                                <span className={styles.media}>
                                    {product.image_url ? <Image src={product.image_url} alt={product.image_alt ?? product.title} width={640} height={640} unoptimized className={styles.productImage} />
                                        : <span className={styles.noImage}>Нет фото</span>}
                                </span>
                                <span className={styles.meta}><span className={styles.title}>{product.title}</span><span className={styles.price}>{product.price}₽</span></span>
                            </button>
                            {isFavorite && <button type="button" className={styles.cardFavorite} disabled={pending || unknown} aria-label={favoriteLabel} aria-pressed={isFavorite} onClick={() => onFavorite(product.id)}>
                                <Icon name="card-favorite" width={12} height={12} />
                            </button>}
                            <div id={actionsId} className={styles.actionsReveal} inert={!isExpanded} aria-hidden={!isExpanded}>
                                <div className={styles.actionsClip}><div className={styles.actions}>
                                    <button type="button" className={styles.like} disabled={pending || unknown} aria-label={favoriteLabel} aria-pressed={isFavorite} onClick={() => onFavorite(product.id)}><Icon name="like" width={19} height={19} filled={isFavorite} /></button>
                                    <Link href={productConstructorHref(product.id)} className={styles.add} aria-label={`${product.title}: создать изделие`}><Icon name="plus" width={17} height={17} /></Link>
                                    <button type="button" className={styles.share} aria-label={`${product.title}: поделиться`} onClick={() => onShare(product)}><Icon name="share" width={17} height={17} /></button>
                                </div></div>
                            </div>
                        </article>;
                    })}
                </div> : <p className={styles.empty} role="status">{label === 'Избранные товары' ? 'В избранном пока пусто. Нажмите на сердечко на карточке товара.' : 'Ничего не найдено'}</p>}
        {status === 'ready' && error != null && <p className={styles.empty} role="alert">{cursorExpired ? error.message : 'Не удалось загрузить следующую страницу.'}</p>}
        {status === 'ready' && hasMore && <button type="button" className={styles.loadMore} disabled={loadingMore} onClick={cursorExpired ? onRetry : onLoadMore}>{loadingMore ? 'Загружаем…' : cursorExpired ? 'Обновить список' : error != null ? 'Повторить загрузку' : 'Показать ещё'}</button>}
    </div>;
}
