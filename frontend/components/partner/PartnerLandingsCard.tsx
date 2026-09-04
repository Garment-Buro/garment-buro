"use client";

import { useState } from 'react';
import { PiArrowSquareOut, PiCheck, PiCopy } from 'react-icons/pi';

import type { PartnerLanding } from '@/lib/partners/types';

import styles from './PartnerDashboard.module.css';

const landingUrl = (slug: string) => `https://garment-buro.ru/p/${slug}`;

export const PartnerLandingsCard = ({ landings }: { landings: PartnerLanding[] }) => {
    const [copiedLandingId, setCopiedLandingId] = useState<number | null>(null);

    const copyLanding = async (landing: PartnerLanding) => {
        try {
            await navigator.clipboard.writeText(landingUrl(landing.slug));
            setCopiedLandingId(landing.id);
            window.setTimeout(() => setCopiedLandingId(null), 1800);
        } catch {
            setCopiedLandingId(null);
        }
    };

    return (
        <section className={styles.panel} aria-labelledby="partner-landings-title">
            <div className={styles.panelHeader}>
                <div>
                    <p className={styles.sectionEyebrow}>Готовые страницы</p>
                    <h2 id="partner-landings-title">Ваши лендинги</h2>
                </div>
            </div>

            {landings.length > 0 ? (
                <div className={styles.landingList}>
                    {landings.map(landing => (
                        <article className={styles.landingRow} key={landing.id}>
                            <div className={styles.landingInfo}>
                                <p className={styles.landingTitle}>{landing.title}</p>
                                <p className={styles.landingUrl}>{landingUrl(landing.slug)}</p>
                            </div>
                            <div className={styles.landingActions}>
                                <button
                                    type="button"
                                    className={styles.iconButton}
                                    onClick={() => void copyLanding(landing)}
                                    aria-label={`Скопировать ссылку на ${landing.title}`}
                                >
                                    {copiedLandingId === landing.id
                                        ? <PiCheck size={18} aria-hidden="true" />
                                        : <PiCopy size={18} aria-hidden="true" />}
                                </button>
                                {landing.status === 'published' && (
                                    <a
                                        className={styles.iconButton}
                                        href={landingUrl(landing.slug)}
                                        target="_blank"
                                        rel="noreferrer"
                                        aria-label={`Открыть ${landing.title}`}
                                    >
                                        <PiArrowSquareOut size={18} aria-hidden="true" />
                                    </a>
                                )}
                            </div>
                        </article>
                    ))}
                </div>
            ) : (
                <p className={styles.emptyText}>
                    Здесь появятся ссылки на опубликованные для вас лендинги.
                </p>
            )}
        </section>
    );
};
