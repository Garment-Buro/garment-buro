import Link from 'next/link';

import { RawMediaImage } from '@/components/shared/RawMediaImage';
import type { PublicPartnerLanding } from '@/lib/partners/types';
import type {CollectionModelsState} from '@/lib/catalog/collection';

import { getLandingCopy } from './content';
import { LandingReveal } from './LandingReveal';
import styles from './CollectionLanding.module.css';

export const CollectionModels = ({
    landing,
    models,
}: {
    landing: PublicPartnerLanding;
    models: CollectionModelsState;
}) => {
    const copy = getLandingCopy(landing);

    return (
        <section id="models" className={styles.modelsSection} aria-labelledby="models-title">
            <LandingReveal className={styles.sectionHeading}>
                <p className={styles.sectionMarker}>Модели коллекции</p>
                <h2 id="models-title">{copy.modelHeading}</h2>
            </LandingReveal>

            {models.status==='error' ? (
                <div className={styles.emptyModels} role="alert">
                    <p>Не удалось загрузить модели коллекции.</p>
                    <form action={`/p/${encodeURIComponent(landing.slug)}#models`} method="get">
                        <button type="submit">Повторить загрузку</button>
                    </form>
                </div>
            ) : models.items.length ? (
                <div className={styles.modelList}>
                    {models.items.map((product, index) => {
                        const image = product.image_url;
                        return (
                            <LandingReveal key={product.id}>
                                <article className={styles.modelFeature}>
                                    <div className={styles.modelMedia}>
                                        {image ? (
                                            <RawMediaImage src={image} alt={product.image_alt ?? product.title} className={styles.coverImage} />
                                        ) : (
                                            <span className={styles.modelNumber}>{String(index + 1).padStart(2, '0')}</span>
                                        )}
                                    </div>
                                    <div className={styles.modelCopy}>
                                        <p className={styles.sectionMarker}>Основа {String(index + 1).padStart(2, '0')}</p>
                                        <h3>{product.title}</h3>
                                        <p>{product.description || 'Выберите посадку, цвет и детали в конструкторе.'}</p>
                                        <div className={styles.modelAction}>
                                            <span>от {Number(product.price).toLocaleString('ru-RU')} ₽</span>
                                            <Link href={`/constructor?productId=${product.id}&landing=${encodeURIComponent(landing.slug)}`}>
                                                Настроить модель
                                            </Link>
                                        </div>
                                    </div>
                                </article>
                            </LandingReveal>
                        );
                    })}
                </div>
            ) : (
                <div className={styles.emptyModels}>
                    <p>Модели для этой коллекции скоро появятся.</p>
                    <Link href={landing.cta_href}>Перейти дальше</Link>
                </div>
            )}
        </section>
    );
};
