import type { Metadata } from 'next';
import { PublicProfileEditor } from '@/components/people/PublicProfileEditor';

export const metadata: Metadata = { title: 'Мой публичный профиль', robots: { index: false, follow: false } };
export const dynamic = 'force-dynamic';

export default function PublicProfileEditorPage() {
    return <PublicProfileEditor />;
}
