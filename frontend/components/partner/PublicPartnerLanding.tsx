import { CollectionLanding } from '@/components/landings/CollectionLanding';
import { PartnerLandingDesktopGate } from '@/components/landings/PartnerLandingDesktopGate';
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
        <div className="partnerLandingMobilePresentation">
            <CollectionLanding landing={landing} products={products} />
        </div>
        <PartnerLandingDesktopGate
            titleId={`partner-landing-${landing.slug}`}
            campaignName={landing.partner_name}
            brandName="Garment Buro"
            backgroundSrc={landing.image_url || '/nikitamoiseev/hero-mobile.png'}
            qrSrc={`/api/qr-code?path=${encodeURIComponent(`/p/${landing.slug}`)}&size=1024`}
            qrAlt={`QR-код для открытия коллекции ${landing.partner_name} на телефоне`}
        />
    </>
);
