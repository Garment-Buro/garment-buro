import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

export const metadata: Metadata = {
    title: 'Производство',
    robots: { index: false, follow: false },
};

export default function ProductionPage() {
    redirect('/admin/crm');
}
