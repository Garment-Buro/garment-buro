import type { Metadata } from 'next';

import { UnfinishedSurface } from '@/components/unfinished/UnfinishedSurface';

export const metadata: Metadata = {
    title: 'Profile',
    robots: { index: false, follow: false },
};

export default function ProfilePage() {
    return <UnfinishedSurface initialTab="profile" />;
}
