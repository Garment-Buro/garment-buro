"use client";

import { useEffect, useState } from 'react';

import { PartnerLandingDesktopGate } from '@/components/landings/PartnerLandingDesktopGate';
import { PresentationSurface } from '@/components/presentation/PresentationSurface';

const DESKTOP_QUERY = '(min-width: 768px)';

export const PlatformEntry = () => {
    const [desktop, setDesktop] = useState<boolean | null>(null);

    useEffect(() => {
        const media = window.matchMedia(DESKTOP_QUERY);
        const update = () => setDesktop(media.matches);
        update();
        media.addEventListener('change', update);
        return () => media.removeEventListener('change', update);
    }, []);

    if (desktop === null) {
        return <div className="min-h-dvh bg-[#e7eef1]" aria-label="Загружаем страницу" aria-busy="true" />;
    }

    if (!desktop) return <PresentationSurface />;

    return (
        <PartnerLandingDesktopGate
            titleId="platform-desktop-title"
            campaignName="Garment Buro"
            brandName="Ваш бренд"
            backgroundSrc="/Шапка.webp"
            qrSrc="/api/qr-code?path=%2F&size=1024"
            qrAlt="QR-код для открытия презентации Garment Buro на телефоне"
            prompt="Откройте презентацию на телефоне"
            hint={<>Отсканируйте QR-код,<br />чтобы открыть презентацию</>}
        />
    );
};
