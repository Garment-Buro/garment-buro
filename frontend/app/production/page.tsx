import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { ProductionTerminal } from '@/components/production/ProductionTerminal';

export const metadata: Metadata = {
    title: 'Производство',
    robots: { index: false, follow: false },
    manifest: '/production/manifest.webmanifest',
};

export default async function ProductionPage({ searchParams }: {
    searchParams: Promise<{ section?: string | string[]; product?: string | string[] }>;
}) {
    const query = await searchParams;
    const presets = query.section === 'presets';
    let initialProduct: number | 'new' | undefined;
    if (presets && query.product !== undefined) {
        if (query.product === 'new') initialProduct = 'new';
        else if (typeof query.product === 'string' && /^[1-9]\d*$/.test(query.product)
            && Number(query.product) <= 2147483647) initialProduct = Number(query.product);
        else notFound();
    }
    return <ProductionTerminal initialSection={presets ? 'presets' : undefined} initialProduct={initialProduct} />;
}
