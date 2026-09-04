import Image from 'next/image';
import type { ReactNode } from 'react';

import styles from './PartnerLandingDesktopGate.module.css';

type PartnerLandingDesktopGateProps = {
    titleId: string;
    campaignName: string;
    brandName: string;
    backgroundSrc: string;
    qrSrc: string;
    logoSrc: string;
    qrAlt: string;
    prompt?: string;
    hint?: ReactNode;
};

export const PartnerLandingDesktopGate = ({
    titleId,
    campaignName,
    brandName,
    backgroundSrc,
    qrSrc,
    logoSrc,
    qrAlt,
    prompt = 'Откройте дроп на телефоне',
    hint = <>Отсканируйте QR-код,<br />чтобы открыть коллекцию</>,
}: PartnerLandingDesktopGateProps) => (
    <section className={styles.gate} aria-labelledby={titleId}>
        <Image
            src={backgroundSrc}
            alt=""
            fill
            priority
            sizes="112vw"
            className={styles.background}
        />
        <div className={styles.wash} aria-hidden="true" />

        <div className={styles.card}>
            <h1 id={titleId} className={styles.brand}>
                <span>{campaignName}</span>
                <small>×<br />{brandName}</small>
            </h1>

            <div className={styles.qrFrame}>
                <Image
                    src={qrSrc}
                    alt={qrAlt}
                    fill
                    priority
                    unoptimized
                    sizes="421px"
                    className={styles.qrImage}
                />
            </div>

            <p className={styles.prompt}>{prompt}</p>
            <div className={styles.hint}>
                <Image src={logoSrc} alt={brandName} width={30} height={30} />
                <p>{hint}</p>
            </div>
        </div>
    </section>
);
