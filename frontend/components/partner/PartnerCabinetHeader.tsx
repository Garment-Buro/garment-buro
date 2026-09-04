import { formatPartnerPercent } from '@/lib/partners/format';
import type { PartnerProfile } from '@/lib/partners/types';

import styles from './PartnerDashboard.module.css';

export const PartnerCabinetHeader = ({ partner }: { partner: PartnerProfile }) => (
    <header className={styles.hero}>
        <div className={styles.heroInner}>
            <div className={styles.heroTopline}>
                <div className={styles.brand} aria-label="Garment Buro">
                    <span className={styles.brandMark} aria-hidden="true">GB</span>
                    <span>
                        <span className={styles.brandName}>Garment Buro</span>
                        <span className={styles.brandContext}>Кабинет партнёра</span>
                    </span>
                </div>
                <span className={styles.locationBadge}>Партнёр</span>
            </div>

            <div className={styles.heroCopy}>
                <p className={styles.eyebrow}>Вы находитесь в партнёрском кабинете</p>
                <h1 className={styles.title}>{partner.display_name}</h1>
                <p className={styles.heroMeta}>
                    Ваша ставка: {formatPartnerPercent(partner.commission_bps)} от подтверждённых продаж
                </p>
            </div>
        </div>
    </header>
);
