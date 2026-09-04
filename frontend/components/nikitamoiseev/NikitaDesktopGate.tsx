import { PartnerLandingDesktopGate } from '@/components/landings/PartnerLandingDesktopGate';

export const NikitaDesktopGate = () => (
    <PartnerLandingDesktopGate
        titleId="nikita-desktop-title"
        campaignName="Nikita Moiseev"
        brandName="Garment Buro"
        backgroundSrc="/nikitamoiseev/hero-mobile.png"
        qrSrc="/api/qr-code?path=%2Fnikitamoiseev&size=1024"
        qrAlt="QR-код для открытия коллекции Nikita Moiseev на телефоне"
    />
);
