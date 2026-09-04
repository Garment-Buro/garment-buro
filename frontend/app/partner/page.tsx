import type { Metadata } from 'next';

import { PartnerPortal } from '@/components/partner/PartnerPortal';

export const metadata: Metadata = {
    title: 'Партнёрский кабинет',
    description: 'Кабинет партнёра GARMENT BURO',
    robots: { index: false, follow: false },
};

export default function PartnerPage() {
    return <PartnerPortal />;
}
