"use client";

import { PartnerDashboard } from '@/components/partner/PartnerDashboard';
import { PartnerLogin } from '@/components/partner/PartnerLogin';
import { useAuthStore } from '@/store/authStore';

export const PartnerPortal = () => {
    const { isAuthenticated, isSessionReady } = useAuthStore();

    if (!isSessionReady) {
        return <div className="flex min-h-dvh items-center justify-center text-sm text-black/50">Восстанавливаем сессию…</div>;
    }

    return isAuthenticated ? <PartnerDashboard /> : <PartnerLogin />;
};
