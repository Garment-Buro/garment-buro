'use client';

import Image from 'next/image';
import Link from 'next/link';
import {communityHref, type Community} from '@/lib/catalog/communities';
import type {FavoriteState} from '@/lib/catalog/favoriteController';
import type {PagedState} from '@/lib/catalog/pagedResource';
import {PageCursorExpiredError} from '@/lib/catalog/pagedResource';
import {ServiceCatalogIcon as Icon} from './ServiceCatalogIcon';
import styles from './ServiceCommunityCatalog.module.css';
import resultStyles from './ServiceSearchResults.module.css';

export function ServiceCommunityGrid({items,status,error,loadingMore,hasMore,onLoadMore,onRetry,membership,onFavorite,label,emptyText='Сообщества не найдены'}:
    Pick<PagedState<Community,unknown>,'items'|'status'|'error'|'loadingMore'> & {
        hasMore:boolean;onLoadMore:()=>void;onRetry:()=>void;label:string;emptyText?:string;
        membership:FavoriteState & {authenticated:boolean;sessionReady:boolean};onFavorite:(id:number)=>void;
    }) {
    const cursorExpired=error instanceof PageCursorExpiredError;
    return <div className={resultStyles.scroller} role="group" tabIndex={0} aria-label={label} aria-busy={status==='loading' || loadingMore}>
        {status==='loading' || status==='idle' ? <p className={styles.empty} role="status">Загружаем сообщества…</p>
            : status==='error' ? <p className={styles.empty} role="alert">Не удалось загрузить сообщества. <button type="button" onClick={onRetry}>Повторить</button></p>
                : items.length ? <div className={styles.grid}>{items.map(community=>{
                    const favorite=membership.ids.includes(community.id);
                    const pending=membership.pendingIds.includes(community.id);
                    const unknown=!membership.sessionReady || (membership.authenticated && !membership.knownIds.includes(community.id));
                    return <article key={community.id} className={styles.card} data-community={community.id}>
                        <Link href={communityHref(community.slug)} prefetch={false} className={styles.summary} aria-label={`${community.title}: открыть сообщество`}>
                            <span className={styles.media}>{community.image_url ? <Image src={community.image_url} alt="" width={480} height={270} unoptimized className={styles.artwork}/>
                                : <span className={styles.placeholder} aria-hidden="true">{community.title.slice(0,1)}</span>}</span>
                            <h3>{community.title}</h3>
                        </Link>
                        <p className={styles.owner}>{community.owner_name}</p>
                        <p className={styles.description}>{community.description}</p>
                        <button type="button" className={styles.favorite} disabled={pending || unknown} aria-label={`${community.title}: ${pending ? 'сохраняем избранное' : unknown ? 'проверяем избранное' : favorite ? 'убрать из избранного' : 'в избранное'}`} aria-pressed={favorite} onClick={()=>onFavorite(community.id)}>
                            <Icon name="like" width={15} height={15} filled={favorite}/>{favorite ? 'В избранном' : 'В избранное'}
                        </button>
                    </article>;
                })}</div> : <p className={styles.empty} role="status">{emptyText}</p>}
        {status==='ready' && error!=null && <p className={styles.empty} role="alert">{cursorExpired ? error.message : 'Не удалось загрузить следующую страницу.'}</p>}
        {status==='ready' && hasMore && <button type="button" className={resultStyles.loadMore} disabled={loadingMore} onClick={cursorExpired ? onRetry : onLoadMore}>{loadingMore ? 'Загружаем…' : cursorExpired ? 'Обновить список' : error!=null ? 'Повторить загрузку' : 'Показать ещё'}</button>}
    </div>;
}
