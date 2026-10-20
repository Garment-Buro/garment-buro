import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { PublicPartnerLanding } from '@/components/partner/PublicPartnerLanding';
import { getPublicPartnerLanding } from '@/lib/api/partners.server';
import {getCollectionProducts} from '@/lib/server/backend/collection';
import type {CollectionModelsState} from '@/lib/catalog/collection';

type PartnerLandingPageProps = {
    params: Promise<{ slug: string }>;
};

// Publication can be revoked by the owner at any time. Selected product reads
// keep their own bounded cache; the landing and page are read per request.
export const revalidate = 0;

export async function generateMetadata({ params }: PartnerLandingPageProps): Promise<Metadata> {
    const { slug } = await params;
    const landing = await getPublicPartnerLanding(slug);
    if (!landing) return { title: 'Страница не найдена', robots: { index: false } };
    return {
        title: landing.title,
        description: landing.description.slice(0, 160),
        robots: { index: true, follow: true },
        alternates: { canonical: `/p/${landing.slug}` },
        openGraph: {
            title: landing.title,
            description: landing.description.slice(0, 160),
            images: landing.image_url ? [landing.image_url] : undefined,
        },
    };
}

export default async function PartnerLandingPage({ params }: PartnerLandingPageProps) {
    const { slug } = await params;
    const landing = await getPublicPartnerLanding(slug);
    if (!landing) notFound();
    let models: CollectionModelsState;
    try {
        models = {status:'ready', items:await getCollectionProducts(landing.product_ids)};
    } catch {
        models = {status:'error'};
    }
    return <PublicPartnerLanding landing={landing} models={models} />;
}
