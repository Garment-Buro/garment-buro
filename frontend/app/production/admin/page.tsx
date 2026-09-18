import type { Metadata } from 'next';
import { permanentRedirect } from 'next/navigation';

export const metadata: Metadata = {
    title: 'Администратор · Garment Buro',
    robots: { index: false, follow: false },
    manifest: '/production/manifest.webmanifest',
};
export default function ProductionAdminPage() {
    permanentRedirect('/production');
}
