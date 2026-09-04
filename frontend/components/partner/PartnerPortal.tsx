"use client";

import { PartnerDashboard } from '@/components/partner/PartnerDashboard';
import { PartnerLogin } from '@/components/partner/PartnerLogin';
import { useAuthStore } from '@/store/authStore';

export const PartnerPortal = () => {
    const { isAuthenticated, isSessionReady } = useAuthStore();

    if (!isSessionReady) {
        return <div className="min-h-dvh bg-[#e7eef1]" aria-label="Восстанавливаем сессию" aria-busy="true" />;
    }

    return isAuthenticated ? <PartnerDashboard /> : <PartnerLogin />;
};
