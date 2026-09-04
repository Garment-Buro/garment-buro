import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { PublicPartnerLanding } from '@/components/partner/PublicPartnerLanding';
import { getPublicPartnerLanding } from '@/lib/api/partners.server';
import { getServerProducts } from '@/lib/api/products.server';

type PartnerLandingPageProps = {
    params: Promise<{ slug: string }>;
};

export const revalidate = 60;

export async function generateMetadata({ params }: PartnerLandingPageProps): Promise<Metadata> {
    const { slug } = await params;
    const landing = await getPublicPartnerLanding(slug).catch(() => null);
    if (!landing) return { title: 'Страница не найдена', robots: { index: false } };
    return {
        title: landing.title,
        description: landing.description.slice(0, 160),
        robots: { index: false, follow: true },
    };
}

export default async function PartnerLandingPage({ params }: PartnerLandingPageProps) {
    const { slug } = await params;
    const [landing, allProducts] = await Promise.all([
        getPublicPartnerLanding(slug).catch(() => null),
        getServerProducts().catch(() => []),
    ]);
    if (!landing) notFound();
    const selectedIds = new Set(landing.product_ids);
    const products = allProducts.filter(product => selectedIds.has(product.id));
    return <PublicPartnerLanding landing={landing} products={products} />;
}
