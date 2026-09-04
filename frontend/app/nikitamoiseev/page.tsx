import type { Metadata } from 'next';

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

export default function NikitaMoiseevPage() {
    return <NikitaMoiseevLanding />;
}
