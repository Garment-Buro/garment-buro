import type { Metadata } from 'next';
import { ServerPlatformEntry } from '@/components/platform/ServerPlatformEntry';

export const metadata: Metadata = {
    title: 'Каталог одежды',
    description: 'Одежда GARMENT BURO для персонализации в конструкторе.',
};

export default function CatalogPage() {
    return <ServerPlatformEntry catalog />;
}
