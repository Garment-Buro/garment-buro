'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';

import { ServiceHomeCart } from './ServiceHomeCart';
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
const personLiza = asset('person-liza.webp', 512, 512);
const personMan = asset('person-man.webp', 320, 400);

const communities = [
    { id: 'runners', name: 'Light Running', image: communityRunners, href: '/light-running' },
    { id: 'heart', name: 'Сообщество с сердцем', image: communityHeart },
    { id: 'boxing', name: 'Box Club', image: communityBoxing },
] as const;

const clothing = [
    { id: 'shoes', name: 'Кеды OG Run', image: clothingShoes },
    { id: 'cap', name: 'Кепка RGM+', image: clothingCap },
    { id: 'top', name: 'Майка Horse Com', image: clothingTop },
] as const;

const matchesSearch = (name: string, query: string) => (
    name.toLocaleLowerCase('ru').includes(query.trim().toLocaleLowerCase('ru'))
);

export function ServiceHome() {
    const [query, setQuery] = useState('');
    const isSearching = query.trim().length > 0;
    const visibleCommunities = communities.filter(item => matchesSearch(item.name, query));
    const visibleClothing = clothing.filter(item => matchesSearch(item.name, query));
    const showLiza = matchesSearch('Liza Kukharskaia @moeimyaliza Лиза Кухарская', query);
    const showSecondPerson = query.trim() === '';
    const hasResults = visibleCommunities.length > 0 || visibleClothing.length > 0 || showLiza || showSecondPerson;
    const showProductResults = isSearching && (hasServiceSearchProducts(query) || !hasResults);

    return (
        <>
            <div className={`${styles.page} ${isSearching ? styles.pageSearch : ''}`}>
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
                            placeholder="А"
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
                                <div className={`${styles.rail} ${styles.communityRail}`} tabIndex={0} role="group" aria-label="Сообщества — прокрутка по горизонтали">
                                    {visibleCommunities.map(community => {
                                        const artwork = (
                                            <>
                                                <Image
                                                    src={community.image}
                                                    alt={community.name}
                                                    loading="eager"
                                                    unoptimized
                                                    className={`${styles.cropImage} ${styles[`${community.id}Image`]}`}
                                                />
                                                {community.id === 'boxing' && <span className={styles.boxingName} aria-hidden="true">BOX<br />CLUB</span>}
                                            </>
                                        );

                                        return 'href' in community ? (
                                            <Link key={community.id} href={community.href} className={`${styles.community} ${styles[community.id]}`}>
                                                {artwork}
                                            </Link>
                                        ) : (
                                            <div key={community.id} className={`${styles.community} ${styles[community.id]}`}>
                                                {artwork}
                                            </div>
                                        );
                                    })}
                                </div>
                            </section>

                            <section className={styles.clothing} aria-labelledby="home-clothing">
                                <h2 id="home-clothing" className={styles.sectionTitle}>ОДЕЖДА</h2>
                                <div className={`${styles.rail} ${styles.clothingRail}`} tabIndex={0} role="group" aria-label="Одежда — прокрутка по горизонтали">
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
                                </div>
                            </section>

                            <section className={styles.people} aria-labelledby="home-people">
                                <h2 id="home-people" className={styles.sectionTitle}>ЛЮДИ</h2>
                                <div className={`${styles.rail} ${styles.peopleRail}`} tabIndex={0} role="group" aria-label="Люди — прокрутка по горизонтали">
                                    {showLiza && (
                                        <article className={styles.personCard}>
                                            <Image src={personLiza} alt="" loading="eager" unoptimized className={`${styles.cropImage} ${styles.personBackdrop}`} />
                                            <div className={styles.personPortrait}>
                                                <Image src={personLiza} alt="Лиза Кухарская" loading="eager" unoptimized className={`${styles.cropImage} ${styles.lizaPortrait}`} />
                                            </div>
                                            <div className={styles.personDetails}>
                                                <h3>LIZA<br />KUKHARSKAIA</h3>
                                                <p>@moeimyaliza</p>
                                            </div>
                                        </article>
                                    )}
                                    {showSecondPerson && (
                                        <div className={styles.personPreview}>
                                            <Image src={personMan} alt="Участник сообщества" loading="eager" unoptimized className={`${styles.cropImage} ${styles.manPortrait}`} />
                                        </div>
                                    )}
                                </div>
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
