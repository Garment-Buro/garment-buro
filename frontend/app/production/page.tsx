import type { Metadata } from 'next';
import { ProductionTerminal } from '@/components/production/ProductionTerminal';

export const metadata: Metadata = {
    title: 'Производство',
    robots: { index: false, follow: false },
    manifest: '/production/manifest.webmanifest',
};

export default function ProductionPage() {
    return <ProductionTerminal />;
}
