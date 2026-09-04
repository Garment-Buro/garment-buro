import type { Metadata, Viewport } from 'next';

import { NikitaMoiseevLanding } from '@/components/nikitamoiseev/NikitaMoiseevLanding';

export const metadata: Metadata = {
    title: 'Nikita Moiseev × Garment Buro',
    description: 'DROP 01 Moving Castle. Настройте худи Nikita Moiseev в конструкторе Garment Buro.',
    robots: { index: true, follow: true },
    alternates: { canonical: '/nikitamoiseev' },
    openGraph: {
        title: 'Nikita Moiseev × Garment Buro',
        description: 'DROP 01 Moving Castle. Настройте худи из совместной коллекции.',
        images: ['/nikitamoiseev/hero-mobile.png'],
    },
};

export const viewport: Viewport = {
    width: 'device-width',
    initialScale: 1,
    viewportFit: 'cover',
    themeColor: '#E8F1F8',
    colorScheme: 'light',
};

export default function NikitaMoiseevPage() {
    return <NikitaMoiseevLanding />;
}
