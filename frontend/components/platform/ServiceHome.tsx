'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';

import { ServiceHomeCart } from './ServiceHomeCart';
import { ServicePersonCard } from './ServicePersonCard';
import { ServicePreviewRail } from './ServicePreviewRail';
import { ServiceSearchResults } from './ServiceSearchResults';
import { ServiceCategoryCatalog } from './ServiceCategoryCatalog';
import { serviceClothing, serviceCommunities, servicePeople, type ServiceCategory } from './serviceHomeData';
import { rankServiceItems } from './serviceSearch';
import styles from './ServiceHome.module.css';

const ASSETS = '/service-home';

export function ServiceHome() {
    const [query, setQuery] = useState('');
    const [category, setCategory] = useState<ServiceCategory | null>(null);
    const expanded = category !== null;
    const visibleCommunities = rankServiceItems(serviceCommunities, query);
    const visibleClothing = rankServiceItems(serviceClothing, query);
    const visiblePeople = rankServiceItems(servicePeople, query);
    const closeCatalog = () => setCategory(null);

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
                                        setCategory(null);
                                        event.currentTarget.blur();
                                    }
                                }}
                                autoComplete="off"
                                spellCheck={false}
                            />
                        </label>

                        {category === 'clothing' ? <ServiceSearchResults query={query} onBack={closeCatalog} />
                            : category ? <ServiceCategoryCatalog category={category} query={query} onBack={closeCatalog} /> : <>
                            <div className={styles.panel}>
                                <section className={styles.communities} aria-labelledby="home-communities">
                                    <h2 id="home-communities" className={styles.sectionTitle}><button type="button" onClick={() => setCategory('communities')}>СООБЩЕСТВА</button></h2>
                                    <ServicePreviewRail resetKey={query} autoPlay={!query.trim()} className={styles.communityRail} label="Сообщества — прокрутка по горизонтали">
                                        {visibleCommunities.map(community => (
                                            <button type="button" key={community.id} className={`${styles.community} ${styles[community.id]}`} aria-label={`${community.name}: открыть каталог сообществ`} onClick={() => setCategory('communities')}>
                                                <Image src={community.image} alt={community.name} loading="eager" unoptimized className={`${styles.cropImage} ${styles[`${community.id}Image`]}`} />
                                                {community.id === 'boxing' && <span className={styles.boxingName} aria-hidden="true">BOX<br />CLUB</span>}
                                            </button>
                                        ))}
                                    </ServicePreviewRail>
                                </section>

                                <section className={styles.clothing} aria-labelledby="home-clothing">
                                    <h2 id="home-clothing" className={styles.sectionTitle}><button type="button" onClick={() => setCategory('clothing')}>ОДЕЖДА</button></h2>
                                    <ServicePreviewRail resetKey={query} autoPlay={!query.trim()} className={styles.clothingRail} label="Одежда — прокрутка по горизонтали">
                                        {visibleClothing.map(item => (
                                            <article key={item.id} className={styles.clothingCard}>
                                                <div className={styles.productFrame}>
                                                    <div className={`${styles.productCrop} ${styles[item.artwork]}`}>
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
                                                <button type="button" className={styles.cardOpen} aria-label={`${item.name}: открыть каталог одежды`} onClick={() => setCategory('clothing')} />
                                            </article>
                                        ))}
                                    </ServicePreviewRail>
                                </section>

                                <section className={styles.people} aria-labelledby="home-people">
                                    <h2 id="home-people" className={styles.sectionTitle}><button type="button" onClick={() => setCategory('people')}>ЛЮДИ</button></h2>
                                    <ServicePreviewRail resetKey={query} autoPlay={!query.trim()} className={styles.peopleRail} label="Люди — прокрутка по горизонтали">
                                        {visiblePeople.map(person => <ServicePersonCard key={person.id} person={person} onOpen={() => setCategory('people')} />)}
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
            </div>
            <ServiceHomeCart />
        </>
    );
}
