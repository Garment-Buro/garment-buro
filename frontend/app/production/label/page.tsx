import type { Metadata } from 'next';
import { PublicBagLabel } from '@/components/production/PublicBagLabel';
export const metadata: Metadata = {
    title: 'Мешок производства',
    robots: { index: false, follow: false },
    referrer: 'no-referrer',
};
export default function Page() {
    return <PublicBagLabel />;
}
