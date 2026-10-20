import Link from 'next/link';

import type { PublicPartnerLanding } from '@/lib/partners/types';
import type {CollectionModelsState} from '@/lib/catalog/collection';

import { CollectionDetails } from './CollectionDetails';
import { CollectionHero } from './CollectionHero';
import { CollectionModels } from './CollectionModels';
import { CollectionStory } from './CollectionStory';
import styles from './CollectionLanding.module.css';

export const CollectionLanding = ({
    landing,
    models,
}: {
    landing: PublicPartnerLanding;
    models: CollectionModelsState;
}) => (
    <div className={styles.page}>
        <a className={styles.skipLink} href="#collection-content">Перейти к коллекции</a>
        <header className={styles.header}>
            <Link href="/" className={styles.wordmark}>GARMENT BURO</Link>
            <p>{landing.partner_name}</p>
            <nav aria-label="Сервисы">
                <Link href="/profile">Профиль</Link>
                <Link href="/checkout">Корзина</Link>
            </nav>
        </header>
        <main id="collection-content">
            <CollectionHero landing={landing} hasModels={models.status==='error' || models.items.length > 0} />
            <CollectionStory landing={landing} />
            <CollectionModels landing={landing} models={models} />
            <CollectionDetails landing={landing} />
        </main>
        <footer className={styles.footer}>
            <p>GARMENT BURO</p>
            <nav aria-label="Правовая информация">
                <Link href="/offer">Оферта</Link>
                <Link href="/policy">Политика</Link>
                <Link href="/contacts">Контакты</Link>
            </nav>
        </footer>
    </div>
);
