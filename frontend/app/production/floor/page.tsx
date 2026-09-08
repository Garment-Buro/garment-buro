import type { Metadata } from 'next';
import { ProductionTerminal } from '@/components/production/ProductionTerminal';

export const metadata: Metadata = {
    title: 'Участки производства',
    robots: { index: false, follow: false },
    manifest: '/production/manifest.webmanifest',
};
export default function ProductionFloorPage() {
    return <ProductionTerminal mode="floor" />;
}
