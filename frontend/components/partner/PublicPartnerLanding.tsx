import { CollectionLanding } from '@/components/landings/CollectionLanding';
import { PartnerLandingDesktopGate } from '@/components/landings/PartnerLandingDesktopGate';
import { PartnerAttributionBootstrap } from '@/components/partner/PartnerAttributionBootstrap';
import type { PublicPartnerLanding as Landing } from '@/lib/partners/types';
import type {CollectionModelsState} from '@/lib/catalog/collection';

type PublicPartnerLandingProps = {
    landing: Landing;
    models: CollectionModelsState;
};

export const PublicPartnerLanding = ({ landing, models }: PublicPartnerLandingProps) => (
    <>
        <PartnerAttributionBootstrap slug={landing.slug} />
        <div className="partnerLandingMobilePresentation">
            <CollectionLanding landing={landing} models={models} />
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
