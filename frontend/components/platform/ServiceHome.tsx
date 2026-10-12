'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';

import { ServiceHomeCart } from './ServiceHomeCart';
import { ServicePersonCard, type ServicePerson } from './ServicePersonCard';
import { ServicePreviewRail } from './ServicePreviewRail';
import { hasServiceSearchProducts, ServiceSearchResults } from './ServiceSearchResults';
import styles from './ServiceHome.module.css';

const ASSETS = '/service-home';
const asset = (filename: string, width: number, height: number) => ({ src: `${ASSETS}/${filename}`, width, height });
// Pre-sized WebP copies keep the Figma artwork local and avoid runtime thumbnail encoding.
const communityRunners = asset('community-runners.webp', 576, 321);
const communityHeart = asset('community-heart.webp', 512, 640);
const communityBoxing = asset('community-boxing.webp', 640, 773);
const clothingShoes = asset('clothing-shoes.webp', 384, 273);
const clothingCap = asset('clothing-cap.webp', 384, 384);
const clothingTop = asset('clothing-top.webp', 384, 384);
const clothingHoodie = asset('search/search-hoodie.webp', 640, 800);
const personLiza = asset('person-liza.webp', 512, 512);
const personMan = asset('person-man.webp', 320, 400);

const communities = [
    { id: 'runners', name: 'Light Running', image: communityRunners },
    { id: 'heart', name: 'Сообщество с сердцем', image: communityHeart },
    { id: 'boxing', name: 'Box Club', image: communityBoxing },
] as const;

const clothing = [
    { id: 'shoes', name: 'Кеды OG Run', image: clothingShoes },
    { id: 'cap', name: 'Кепка RGM+', image: clothingCap },
    { id: 'top', name: 'Майка Horse Com', image: clothingTop },
    { id: 'hoodie', name: 'Худи', image: clothingHoodie },
] as const;

const people: ServicePerson[] = [
    { id: 'liza', name: 'LIZA KUKHARSKAIA', subtitle: '@moeimyaliza', image: personLiza, portrait: 'lizaPortrait' },
    { id: 'member', name: 'УЧАСТНИК СООБЩЕСТВА', subtitle: 'Garment Buro', image: personMan, portrait: 'manPortrait' },
];

const matchesSearch = (name: string, query: string) => (
    name.toLocaleLowerCase('ru').includes(query.trim().toLocaleLowerCase('ru'))
);

export function ServiceHome() {
    const [query, setQuery] = useState('');
    const isSearching = query.trim().length > 0;
    const visibleCommunities = communities.filter(item => matchesSearch(item.name, query));
    const visibleClothing = clothing.filter(item => matchesSearch(item.name, query));
    const visiblePeople = people.filter(person => matchesSearch(`${person.name} ${person.subtitle} ${person.id === 'liza' ? 'Лиза Кухарская' : ''}`, query));
    const hasResults = visibleCommunities.length > 0 || visibleClothing.length > 0 || visiblePeople.length > 0;
    const showProductResults = isSearching && (hasServiceSearchProducts(query) || !hasResults);

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
            <div className={`${styles.page} ${isSearching ? styles.pageSearch : ''}`} data-service-view={showProductResults ? 'catalog' : 'home'}>

                {/* The cart measures the site header; this decorative wordmark is page content. */}
                <div className={styles.header}>
                    <h1 className={styles.wordmark} aria-label="Garment Buro">
                        <span>GARMENT</span><span>BURO</span>
                    </h1>
                </div>

                <div className={styles.content}>
                    <label className={styles.search}>
                        <Image src={`${ASSETS}/search.svg`} alt="" width={8.839} height={12.239} className={styles.searchIcon} />
                        <input
                            type="search"
                            aria-label="Поиск сообществ, одежды и людей"
                            value={query}
                            onChange={event => setQuery(event.target.value)}
                            autoComplete="off"
                            spellCheck={false}
                        />
                    </label>

                    {showProductResults ? <ServiceSearchResults query={query} onBack={() => setQuery('')} /> : <>
                        <div className={styles.panel}>
                            <section className={styles.communities} aria-labelledby="home-communities">
                                <h2 id="home-communities" className={styles.sectionTitle}>СООБЩЕСТВА</h2>
                                <ServicePreviewRail className={styles.communityRail} label="Сообщества — прокрутка по горизонтали">
                                    {visibleCommunities.map(community => (
                                        <div key={community.id} className={`${styles.community} ${styles[community.id]}`}>
                                            <Image src={community.image} alt={community.name} loading="eager" unoptimized className={`${styles.cropImage} ${styles[`${community.id}Image`]}`} />
                                            {community.id === 'boxing' && <span className={styles.boxingName} aria-hidden="true">BOX<br />CLUB</span>}
                                        </div>
                                    ))}
                                </ServicePreviewRail>
                            </section>

                            <section className={styles.clothing} aria-labelledby="home-clothing">
                                <h2 id="home-clothing" className={styles.sectionTitle}>ОДЕЖДА</h2>
                                <ServicePreviewRail className={styles.clothingRail} label="Одежда — прокрутка по горизонтали">
                                    {visibleClothing.map(item => (
                                        <article key={item.id} className={styles.clothingCard}>
                                            <div className={styles.productFrame}>
                                                <div className={`${styles.productCrop} ${styles[item.id]}`}>
                                                    <Image
                                                        src={item.image}
                                                        alt={item.name}
                                                        loading="eager"
                                                        unoptimized
                                                        className={styles.cropImage}
                                                    />
                                                </div>
                                            </div>
                                            <h3>{item.name}</h3>
                                        </article>
                                    ))}
                                </ServicePreviewRail>
                            </section>

                            <section className={styles.people} aria-labelledby="home-people">
                                <h2 id="home-people" className={styles.sectionTitle}>ЛЮДИ</h2>
                                <ServicePreviewRail className={styles.peopleRail} label="Люди — прокрутка по горизонтали">
                                    {visiblePeople.map(person => <ServicePersonCard key={person.id} person={person} />)}
                                </ServicePreviewRail>
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
            <ServiceHomeCart />
        </>
    );
}
