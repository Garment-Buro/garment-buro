import Link from 'next/link';

import { RawMediaImage } from '@/components/shared/RawMediaImage';
import type { PublicPartnerLanding } from '@/lib/partners/types';
import type { ProductData } from '@/lib/products/types';

import { getLandingCopy } from './content';
import { LandingReveal } from './LandingReveal';
import styles from './CollectionLanding.module.css';

const productImage = (product: ProductData) => (
    product.desktop_video_poster
    || product.mobile_video_poster
    || product.mobile_card_image
    || product.image_left
    || null
);

export const CollectionModels = ({
    landing,
    products,
}: {
    landing: PublicPartnerLanding;
    products: ProductData[];
}) => {
    const copy = getLandingCopy(landing);

    return (
        <section id="models" className={styles.modelsSection} aria-labelledby="models-title">
            <LandingReveal className={styles.sectionHeading}>
                <p className={styles.sectionMarker}>Модели коллекции</p>
                <h2 id="models-title">{copy.modelHeading}</h2>
            </LandingReveal>

            {products.length ? (
                <div className={styles.modelList}>
                    {products.map((product, index) => {
                        const image = productImage(product);
                        return (
                            <LandingReveal key={product.id}>
                                <article className={styles.modelFeature}>
                                    <div className={styles.modelMedia}>
                                        {image ? (
                                            <RawMediaImage src={image} alt={product.title} className={styles.coverImage} />
                                        ) : (
                                            <span className={styles.modelNumber}>{String(index + 1).padStart(2, '0')}</span>
                                        )}
                                    </div>
                                    <div className={styles.modelCopy}>
                                        <p className={styles.sectionMarker}>Основа {String(index + 1).padStart(2, '0')}</p>
                                        <h3>{product.title}</h3>
                                        <p>{product.description || 'Выберите посадку, цвет и детали в конструкторе.'}</p>
                                        <div className={styles.modelAction}>
                                            <span>от {product.price.toLocaleString('ru-RU')} ₽</span>
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
