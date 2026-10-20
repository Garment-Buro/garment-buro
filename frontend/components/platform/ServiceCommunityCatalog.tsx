'use client';

import dynamic from 'next/dynamic';
import {useId,useRef,useState} from 'react';
import {useCommunities} from '@/hooks/catalog/useCommunities';
import {useCommunityFavorites,useSavedCommunities} from '@/hooks/catalog/useCommunityFavorites';
import {ServiceCatalogIcon as Icon} from './ServiceCatalogIcon';
import {ServiceCommunityGrid} from './ServiceCommunityGrid';
import {ServiceFavoritesSheet} from './ServiceFavoritesSheet';
import resultStyles from './ServiceSearchResults.module.css';
import styles from './ServiceCommunityCatalog.module.css';

const AuthPopup=dynamic(()=>import('@/components/auth/AuthPopup').then(module=>module.AuthPopup));

export function ServiceCommunityCatalog({query,onBack}:{query:string;onBack:()=>void}) {
    const [favoritesOpen,setFavoritesOpen]=useState(false);
    const [authOpen,setAuthOpen]=useState(false);
    const [sortOpen,setSortOpen]=useState(false);
    const [sort,setSort]=useState<'newest'|'name'>('newest');
    const sortId=useId();
    const sortButtonRef=useRef<HTMLButtonElement>(null);
    const catalog=useCommunities({query,sort,limit:24});
    const saved=useSavedCommunities(favoritesOpen);
    const membership=useCommunityFavorites([...catalog.items,...saved.items].map(item=>item.id));
    const selectSort=(value:'newest'|'name')=>{setSort(value);setSortOpen(false);sortButtonRef.current?.focus()};
    const openAuth=()=>{setFavoritesOpen(false);setAuthOpen(true)};
    const toggleFavorite=async(id:number)=>{
        if(!membership.authenticated) {openAuth();return}
        if(await membership.toggle(id) && favoritesOpen) void saved.retry();
    };
    const favoriteError=membership.error!=null && <p className={resultStyles.favoriteError} role="alert">Не удалось обновить избранное. <button type="button" onClick={()=>{void membership.retry()}}>Повторить проверку</button></p>;
    const actions={membership,onFavorite:(id:number)=>{void toggleFavorite(id)}};

    return <>
        <section className={resultStyles.results} aria-labelledby="community-catalog-title">
            <div className={resultStyles.toolbar}>
                <button type="button" onClick={onBack} aria-label="Вернуться на главную"><Icon name="back" width={15} height={13}/></button>
                <h2 id="community-catalog-title">СООБЩЕСТВА</h2>
                <button ref={sortButtonRef} type="button" className={resultStyles.sort} aria-label="Порядок сообществ" aria-expanded={sortOpen} aria-controls={sortId} data-active={sort==='name'} onClick={()=>setSortOpen(!sortOpen)}>
                    <Icon name="sort-up" width={8.57895} height={11.7368}/><span className={resultStyles.sortDown}><Icon name="sort-down" width={8.57895} height={11.7368}/></span>
                </button>
                <button type="button" aria-label="Избранные сообщества" aria-haspopup="dialog" aria-expanded={favoritesOpen} disabled={!membership.sessionReady} onClick={()=>{
                    if(membership.authenticated) setFavoritesOpen(true);else openAuth();
                }}><Icon name="favorites" width={12} height={12}/></button>
            </div>
            {sortOpen && <fieldset id={sortId} className={styles.sortOptions}>
                <legend className="sr-only">Порядок сообществ</legend>
                <label><input type="radio" name={sortId} checked={sort==='newest'} onChange={()=>selectSort('newest')}/>Сначала новые</label>
                <label><input type="radio" name={sortId} checked={sort==='name'} onChange={()=>selectSort('name')}/>По названию</label>
            </fieldset>}
            {favoriteError}
            <ServiceCommunityGrid {...actions} {...catalog} label="Каталог: сообщества" hasMore={catalog.nextCursor!==null} onLoadMore={()=>{void catalog.loadMore()}} onRetry={()=>{void catalog.retry()}}/>
        </section>
        {favoritesOpen && <ServiceFavoritesSheet count={saved.authenticated ? saved.items.length : 0} hasMore={saved.authenticated && saved.nextCursor!==null} countLabel="Загружено сообществ из избранного" onClose={()=>setFavoritesOpen(false)}>
            <div className={styles.favoritesContent}>
                {saved.authenticated ? <ServiceCommunityGrid {...actions} {...saved} label="Избранные сообщества" emptyText="В избранном пока пусто. Нажмите на сердечко на карточке сообщества." hasMore={saved.nextCursor!==null} onLoadMore={()=>{void saved.loadMore()}} onRetry={()=>{void saved.retry()}}/>
                    : <p className={styles.empty}>Войдите, чтобы посмотреть избранное. <button type="button" onClick={openAuth}>Войти</button></p>}
                {favoriteError}
            </div>
        </ServiceFavoritesSheet>}
        {authOpen && <AuthPopup isOpen onClose={()=>setAuthOpen(false)}/>}
    </>;
}
