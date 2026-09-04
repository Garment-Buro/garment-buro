import Image from 'next/image';
import Link from 'next/link';

import { NikitaCartAction } from './NikitaCartAction';
import { NikitaHoodieCarousel } from './NikitaHoodieCarousel';
import styles from './NikitaMoiseevLanding.module.css';

export const NikitaMobileDrop = () => (
    <div id="nikita-drop" className={styles.mobileDrop}>
        <section className={styles.mobileHero} aria-labelledby="nikita-mobile-title">
            <div className={styles.mobileHeroImage}>
                <Image
                    src="/nikitamoiseev/hero-mobile.png"
                    alt="Moving Castle"
                    fill
                    priority
                    sizes="(max-width: 767px) 194vw, 0px"
                    className={styles.heroImage}
                />
                <div className={styles.mobileHeroFade} aria-hidden="true" />
            </div>

            <h1 id="nikita-mobile-title" className={styles.mobileBrand}>
                <span>Nikita Moiseev</span>
                <small>×<br />Garment Buro</small>
            </h1>
            <p className={styles.dropNumber}>DROP&nbsp; 01</p>

            <p className={styles.movingCastle} aria-label="Moving Castle">
                <span aria-hidden="true">MOVING</span>
                <span aria-hidden="true">CASTLE</span>
            </p>

            <NikitaHoodieCarousel />
        </section>

        <section id="nikita-merch-start" className={styles.mobileStory} aria-label="Коллекция Moving Castle">
            <div className={styles.ctaDecor} aria-hidden="true">
                <span />
                <span />
            </div>
            <Link
                href="/constructor?productId=5&landing=nikitamoiseev"
                prefetch={false}
                className={styles.customizeButton}
            >
                <span>Настроить мерч</span>
                <Image src="/nikitamoiseev/arrow.svg" alt="" width={22} height={17} />
            </Link>

            <div className={styles.collectionNames} aria-hidden="true">
                <p>NIKITA<br />MOISEEV</p>
                <p>GARMENT<br />BURO</p>
            </div>

            <div className={styles.storyImage}>
                <Image
                    src="/nikitamoiseev/hoodie-back-model.png"
                    alt="Худи Moving Castle из коллекции Nikita Moiseev"
                    fill
                    sizes="(max-width: 767px) 108vw, 0px"
                    className={styles.storyImageAsset}
                />
            </div>
        </section>

        <NikitaCartAction />
    </div>
);
