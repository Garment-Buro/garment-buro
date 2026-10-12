'use client';

import Image from 'next/image';
import { useId, useRef, useState } from 'react';

import { useServiceFavoritesStore } from '@/store/serviceFavoritesStore';
import { ServiceCatalogIcon as Icon } from './ServiceCatalogIcon';
import { ServiceFavoritesSheet } from './ServiceFavoritesSheet';
import { serviceCommunityCards, serviceCommunityCatalog } from './serviceHomeData';
import { rankServiceItems } from './serviceSearch';
import resultStyles from './ServiceSearchResults.module.css';
import styles from './ServiceCommunityCatalog.module.css';

type Community = typeof serviceCommunityCards[number];
type Card = Community & { instanceId: string };
const favoriteId = (community: Community) => `community:${community.id}`;

function CommunityGrid({ items, favorites, onFavorite, emptyText }: {
    items: readonly Card[];
    favorites: readonly string[];
    onFavorite: (id: string) => void;
    emptyText?: string;
}) {
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const gridId = useId();
    return <div className={styles.grid}>
        {items.map(community => {
            const expanded = expandedId === community.instanceId;
            const favorite = favorites.includes(favoriteId(community));
            const actionsId = `${gridId}-${community.instanceId}`;
            return <article key={community.instanceId} className={styles.card}>
                <button type="button" className={styles.summary} aria-label={`${community.name}: ${expanded ? 'свернуть' : 'раскрыть'} карточку`} aria-expanded={expanded} aria-controls={actionsId} onClick={() => setExpandedId(expanded ? null : community.instanceId)}>
                    <Image src={community.artwork} alt={community.name} unoptimized className={styles.artwork} />
                </button>
                <div id={actionsId} className={styles.actionsReveal} data-expanded={expanded} inert={!expanded} aria-hidden={!expanded}>
                    <div className={styles.actionsClip}>
                        <button type="button" className={styles.favorite} aria-label={`${community.name}: ${favorite ? 'убрать из избранного' : 'в избранное'}`} aria-pressed={favorite} onClick={() => onFavorite(favoriteId(community))}>
                            <Icon name="like" width={15} height={15} filled={favorite} />
                            {favorite ? 'В избранном' : 'В избранное'}
                        </button>
                    </div>
                </div>
            </article>;
        })}
        {!items.length && <p className={styles.empty} role="status">{emptyText}</p>}
    </div>;
}

export function ServiceCommunityCatalog({ query, onBack }: { query: string; onBack: () => void }) {
    const favorites = useServiceFavoritesStore(state => state.ids);
    const toggleFavorite = useServiceFavoritesStore(state => state.toggle);
    const [favoritesOpen, setFavoritesOpen] = useState(false);
    const [sortOpen, setSortOpen] = useState(false);
    const [sort, setSort] = useState<'relevance' | 'name'>('relevance');
    const sortId = useId();
    const sortButtonRef = useRef<HTMLButtonElement>(null);
    const selectSort = (value: 'relevance' | 'name') => {
        setSort(value);
        setSortOpen(false);
        sortButtonRef.current?.focus();
    };
    const ordered = rankServiceItems(serviceCommunityCatalog, query);
    const items = sort === 'name' ? [...ordered].sort((a, b) => a.name.localeCompare(b.name, 'ru')) : ordered;
    const favoriteItems = rankServiceItems(serviceCommunityCards.filter(community => favorites.includes(favoriteId(community))), query)
        .map(community => ({ ...community, instanceId: community.id }));

    return <>
        <section className={resultStyles.results} aria-labelledby="community-catalog-title">
            <div className={resultStyles.toolbar}>
                <button type="button" onClick={onBack} aria-label="Вернуться на главную"><Icon name="back" width={15} height={13} /></button>
                <h2 id="community-catalog-title">СООБЩЕСТВА</h2>
                <button ref={sortButtonRef} type="button" className={resultStyles.sort} aria-label="Порядок сообществ" aria-expanded={sortOpen} aria-controls={sortId} data-active={sort === 'name'} onClick={() => setSortOpen(!sortOpen)}>
                    <Icon name="sort-up" width={8.57895} height={11.7368} /><span className={resultStyles.sortDown}><Icon name="sort-down" width={8.57895} height={11.7368} /></span>
                </button>
                <button type="button" aria-label="Избранные сообщества" aria-haspopup="dialog" aria-expanded={favoritesOpen} onClick={() => setFavoritesOpen(true)}><Icon name="favorites" width={12} height={12} /></button>
            </div>
            {sortOpen && <fieldset id={sortId} className={styles.sortOptions}>
                <legend className="sr-only">Порядок сообществ</legend>
                <label><input type="radio" name={sortId} checked={sort === 'relevance'} onChange={() => selectSort('relevance')} />По соответствию</label>
                <label><input type="radio" name={sortId} checked={sort === 'name'} onChange={() => selectSort('name')} />По названию</label>
            </fieldset>}
            <div className={resultStyles.scroller} role="group" tabIndex={0} aria-label="Каталог: сообщества">
                <CommunityGrid items={items} favorites={favorites} onFavorite={toggleFavorite} />
            </div>
        </section>
        {favoritesOpen && <ServiceFavoritesSheet count={favoriteItems.length} countLabel="Сообществ в избранном" onClose={() => setFavoritesOpen(false)}>
            <div className={styles.favoritesContent}>
                <CommunityGrid items={favoriteItems} favorites={favorites} onFavorite={toggleFavorite} emptyText="В избранном пока пусто. Раскройте карточку сообщества и нажмите на сердечко." />
            </div>
        </ServiceFavoritesSheet>}
    </>;
}
