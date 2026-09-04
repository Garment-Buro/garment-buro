import { RawMediaImage } from '@/components/shared/RawMediaImage';
import type { PublicPartnerLanding } from '@/lib/partners/types';

import { getLandingCopy } from './content';
import { LandingReveal, LandingWordReveal } from './LandingReveal';
import styles from './CollectionLanding.module.css';

export const CollectionStory = ({ landing }: { landing: PublicPartnerLanding }) => {
    const copy = getLandingCopy(landing);

    return (
        <>
            <section className={styles.story} aria-labelledby="story-title">
                <LandingReveal>
                    <p className={styles.sectionMarker}>Совместная коллекция</p>
                    <h2 id="story-title">{copy.storyTitle}</h2>
                    <p>{copy.storyBody}</p>
                </LandingReveal>
                {landing.content.secondary_image_url && (
                    <LandingReveal className={styles.storyMedia}>
                        <RawMediaImage
                            src={landing.content.secondary_image_url}
                            alt={`Коллекция ${landing.title}`}
                            className={styles.coverImage}
                        />
                    </LandingReveal>
                )}
            </section>
            <section className={styles.taglineSection} aria-label="Идея коллекции">
                <LandingWordReveal text={copy.finalHeading} />
            </section>
        </>
    );
};
