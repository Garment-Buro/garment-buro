import Link from 'next/link';

import { RawMediaImage } from '@/components/shared/RawMediaImage';
import type { PublicPartnerLanding } from '@/lib/partners/types';

import { getLandingCopy } from './content';
import styles from './CollectionLanding.module.css';

export const CollectionHero = ({ landing, hasModels }: { landing: PublicPartnerLanding; hasModels: boolean }) => {
    const copy = getLandingCopy(landing);
    const heroHref = hasModels ? '#models' : landing.cta_href;

    return (
        <section className={styles.hero} aria-labelledby="collection-title">
            <div className={styles.heroCopy}>
                <p className={styles.eyebrow}>{landing.eyebrow || `${landing.partner_name} × GARMENT BURO`}</p>
                <h1 id="collection-title" className={styles.heroTitle}>{landing.headline}</h1>
                <p className={styles.heroDescription}>{landing.description}</p>
                <Link className={styles.primaryButton} href={heroHref}>{landing.cta_label}</Link>
                <p className={styles.proof}>{copy.proofLine}</p>
            </div>

            <div className={styles.heroMedia}>
                {landing.image_url ? (
                    <RawMediaImage src={landing.image_url} alt={landing.title} className={styles.coverImage} />
                ) : (
                    <span className={styles.heroMonogram} aria-hidden="true">
                        {landing.partner_name.slice(0, 2).toUpperCase()}
                    </span>
                )}
                {landing.content.logo_url && (
                    <RawMediaImage
                        src={landing.content.logo_url}
                        alt={`Логотип ${landing.partner_name}`}
                        className={styles.partnerLogo}
                    />
                )}
            </div>
        </section>
    );
};
