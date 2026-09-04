import Link from 'next/link';

import type { PublicPartnerLanding } from '@/lib/partners/types';

import { getLandingCopy } from './content';
import { LandingReveal } from './LandingReveal';
import styles from './CollectionLanding.module.css';

const steps = [
    ['01', 'Выберите модель', 'Автор коллекции уже отобрал основы, которые подходят её идее.'],
    ['02', 'Настройте изделие', 'Измените посадку, цвет и детали, затем сохраните свой вариант.'],
    ['03', 'Оформите заказ', 'Войдите в аккаунт, выберите доставку и следите за производством.'],
];

export const CollectionDetails = ({ landing }: { landing: PublicPartnerLanding }) => {
    const copy = getLandingCopy(landing);

    return (
        <>
            <section className={styles.stepsSection} aria-labelledby="steps-title">
                <LandingReveal className={styles.sectionHeading}>
                    <p className={styles.sectionMarker}>Как это работает</p>
                    <h2 id="steps-title">От идеи до готовой вещи</h2>
                </LandingReveal>
                <div className={styles.steps}>
                    {steps.map(([number, title, description]) => (
                        <LandingReveal key={number}>
                            <article className={styles.step}>
                                <span>{number}</span>
                                <h3>{title}</h3>
                                <p>{description}</p>
                            </article>
                        </LandingReveal>
                    ))}
                </div>
            </section>

            <section className={styles.faqSection} aria-labelledby="faq-title">
                <LandingReveal className={styles.sectionHeading}>
                    <p className={styles.sectionMarker}>Ответы</p>
                    <h2 id="faq-title">Перед тем как начать</h2>
                </LandingReveal>
                <div className={styles.faqList}>
                    {copy.faq.map(item => (
                        <details key={item.question} className={styles.faqItem}>
                            <summary>{item.question}</summary>
                            <p>{item.answer}</p>
                        </details>
                    ))}
                </div>
            </section>

            <section className={styles.finalCta} aria-labelledby="final-title">
                <LandingReveal>
                    <p className={styles.sectionMarker}>{landing.partner_name} × GARMENT BURO</p>
                    <h2 id="final-title">{copy.finalHeading}</h2>
                    <Link className={styles.secondaryButton} href="#models">{landing.cta_label}</Link>
                </LandingReveal>
            </section>
        </>
    );
};
