import { CollectionLanding } from '@/components/landings/CollectionLanding';
import { PartnerAttributionBootstrap } from '@/components/partner/PartnerAttributionBootstrap';
import type { PublicPartnerLanding as Landing } from '@/lib/partners/types';
import type { ProductData } from '@/lib/products/types';

type PublicPartnerLandingProps = {
    landing: Landing;
    products: ProductData[];
};

export const PublicPartnerLanding = ({ landing, products }: PublicPartnerLandingProps) => (
    <>
        <PartnerAttributionBootstrap slug={landing.slug} />
        <CollectionLanding landing={landing} products={products} />
    </>
);
