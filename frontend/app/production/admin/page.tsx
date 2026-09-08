import type { Metadata } from 'next';
import { ProductionTerminal } from '@/components/production/ProductionTerminal';

export const metadata: Metadata = {
    title: 'Администратор · Garment Buro',
    robots: { index: false, follow: false },
    manifest: '/production/manifest.webmanifest',
};
export default function ProductionAdminPage() {
    return <ProductionTerminal mode="admin" />;
}
