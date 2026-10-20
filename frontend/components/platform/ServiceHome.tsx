'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useStorefrontProducts } from '@/hooks/catalog/useStorefrontProducts';
import {useCommunities} from '@/hooks/catalog/useCommunities';
import {usePeople} from '@/hooks/people/usePeople';
import type {PeopleInitial} from '@/lib/catalog/people';
import type {StorefrontInitial} from '@/lib/catalog/storefront';
import {communityHref, type CommunityInitial} from '@/lib/catalog/communities';

import { ServiceHomeCart } from './ServiceHomeCart';
import { ServicePersonCard } from './ServicePersonCard';
import { ServicePreviewRail } from './ServicePreviewRail';
import { ServiceSearchResults } from './ServiceSearchResults';
import { ServiceCategoryCatalog } from './ServiceCategoryCatalog';
import type { ServiceCategory } from './serviceHomeData';
import styles from './ServiceHome.module.css';

const ASSETS = '/service-home';

export function ServiceHome({ initialCategory = null, initialProducts, initialCommunities, initialPeople }: { initialCategory?:ServiceCategory | null; initialProducts?:StorefrontInitial; initialCommunities?:CommunityInitial; initialPeople?:PeopleInitial }) {
    const router = useRouter();
    const [query, setQuery] = useState('');
    const [category, setCategory] = useState<ServiceCategory | null>(initialCategory);
    const expanded = category !== null;
    const communities=useCommunities({query,limit:4},category===null,initialCommunities);
    const clothing = useStorefrontProducts({query, limit:4}, category === null, initialProducts);
    const people = usePeople({query,limit:4}, category===null, initialPeople);
    const closeCatalog = () => {
        setCategory(null);
        if (initialCategory !== null) router.replace('/');
    };

    return (
        <>
            {/* Outside the clipped content so the artwork continues into safe areas. */}
            <div className={styles.backdrop} aria-hidden="true">
                <Image
                    src={`${ASSETS}/background.webp`}
                    alt=""
                    fill
                    preload
                    unoptimized
                    className={styles.backgroundImage}
                />
            </div>
            <div className={`${styles.page} ${expanded ? styles.pageCatalog : ''}`} data-service-view={category ? 'catalog' : 'home'}>

                {/* The cart measures the site header; this decorative wordmark is page content. */}
                <div className={styles.header}>
                    <h1 className={styles.wordmark} aria-label="Garment Buro">
                        <span>GARMENT</span><span>BURO</span>
                    </h1>
                </div>

                <div className={styles.stage}>
                    <div className={styles.content}>
                        <label className={styles.search}>
                            <Image src={`${ASSETS}/search.svg`} alt="" width={8.839} height={12.239} className={styles.searchIcon} />
                            <input
                                type="search"
                                aria-label="Поиск сообществ, одежды и людей"
                                value={query}
                                onChange={event => setQuery(event.target.value)}
                                onKeyDown={event => {
                                    if (event.key === 'Escape') {
                                        setQuery('');
                                        closeCatalog();
                                        event.currentTarget.blur();
                                    }
                                }}
                                autoComplete="off"
                                spellCheck={false}
                                maxLength={200}
                            />
                        </label>

                        {category === 'clothing' ? <ServiceSearchResults query={query} onBack={closeCatalog} initialProducts={initialProducts} />
                            : category ? <ServiceCategoryCatalog category={category} query={query} onBack={closeCatalog} /> : <>
                            <div className={styles.panel}>
                                <section className={styles.communities} aria-labelledby="home-communities">
                                    <h2 id="home-communities" className={styles.sectionTitle}><button type="button" onClick={() => setCategory('communities')}>СООБЩЕСТВА</button></h2>
                                    <ServicePreviewRail resetKey={query} autoPlay={!query.trim()} className={styles.communityRail} label="Сообщества — прокрутка по горизонтали">
                                        {communities.items.map(community => (
                                            <Link key={community.id} href={communityHref(community.slug)} prefetch={false} data-home-community={community.id} className={styles.community} aria-label={`${community.title}: открыть сообщество`}>
                                                {community.image_url && <Image src={community.image_url} alt="" width={480} height={270} loading="eager" unoptimized className={styles.communityImage}/>}
                                                <span className={styles.communityTitle}>{community.title}</span>
                                            </Link>
                                        ))}
                                    </ServicePreviewRail>
                                    {communities.status==='loading' && <p className={styles.productStatus} role="status">Загружаем сообщества…</p>}
                                    {communities.status==='error' && <p className={styles.productStatus} role="alert">Не удалось загрузить сообщества. <button type="button" onClick={()=>{void communities.retry()}}>Повторить</button></p>}
                                    {communities.status==='ready' && !communities.items.length && <p className={styles.productStatus} role="status">Сообщества не найдены</p>}
                                </section>

                                <section className={styles.clothing} aria-labelledby="home-clothing">
                                    <h2 id="home-clothing" className={styles.sectionTitle}><button type="button" onClick={() => setCategory('clothing')}>ОДЕЖДА</button></h2>
                                    <ServicePreviewRail resetKey={query} autoPlay={!query.trim()} direction="right" className={styles.clothingRail} label="Одежда — прокрутка по горизонтали">
                                        {clothing.items.map(item => (
                                            <article key={item.id} className={styles.clothingCard} data-home-product={item.id}>
                                                <div className={styles.productFrame}>
                                                    {item.image_url ? <Image src={item.image_url} alt={item.image_alt ?? item.title} width={384} height={384} unoptimized className={styles.storefrontImage} />
                                                        : <span className={styles.noProductImage}>Нет фото</span>}
                                                </div>
                                                <h3>{item.title}</h3>
                                                <button type="button" className={styles.cardOpen} aria-label={`${item.title}: открыть каталог одежды`} onClick={() => setCategory('clothing')} />
                                            </article>
                                        ))}
                                    </ServicePreviewRail>
                                    {clothing.status === 'loading' && <p className={styles.productStatus} role="status">Загружаем одежду…</p>}
                                    {clothing.status === 'error' && <p className={styles.productStatus} role="alert">Не удалось загрузить одежду. <button type="button" onClick={() => {void clothing.retry()}}>Повторить</button></p>}
                                    {clothing.status === 'ready' && !clothing.items.length && <p className={styles.productStatus} role="status">Одежда не найдена</p>}
                                </section>

                                <section className={styles.people} aria-labelledby="home-people">
                                    <h2 id="home-people" className={styles.sectionTitle}><button type="button" onClick={() => setCategory('people')}>ЛЮДИ</button></h2>
                                    <ServicePreviewRail resetKey={query} autoPlay={!query.trim()} className={styles.peopleRail} label="Люди — прокрутка по горизонтали">
                                        {people.items.map(person => <ServicePersonCard key={person.id} person={person} />)}
                                    </ServicePreviewRail>
                                    {people.status==='loading' && <p className={styles.productStatus} role="status">Загружаем людей…</p>}
                                    {people.status==='error' && <p className={styles.productStatus} role="alert">Не удалось загрузить людей. <button type="button" onClick={()=>{void people.retry()}}>Повторить</button></p>}
                                    {people.status==='ready' && !people.items.length && <p className={styles.productStatus} role="status">Люди не найдены</p>}
                                </section>

                            </div>

                            <div className={styles.createPanel}>
                                <Link href="/constructor" className={styles.createButton} aria-label="Создать своё изделие">
                                    <span aria-hidden="true">+</span>
                                </Link>
                            </div>
                        </>}
                    </div>
                </div>
            </div>
            <ServiceHomeCart />
        </>
    );
}
