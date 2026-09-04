import type { Metadata } from 'next';

import { UnfinishedSurface } from '@/components/unfinished/UnfinishedSurface';

export const metadata: Metadata = {
    title: 'My collection',
    robots: { index: false, follow: false },
};

export default function MyCollectionPage() {
    return <UnfinishedSurface initialTab="my-collection" />;
}
