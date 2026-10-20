"use client";

import { PartnerDashboard } from '@/components/partner/PartnerDashboard';
import { PartnerLogin } from '@/components/partner/PartnerLogin';
import { useAuthStore } from '@/store/authStore';
import { useCustomerAccount } from '@/hooks/catalog/customerSession';

export const PartnerPortal = () => {
    const { isAuthenticated, isSessionReady } = useAuthStore();
    const account = useCustomerAccount();

    if (!isSessionReady) {
        return <div className="min-h-dvh bg-[#e7eef1]" aria-label="Восстанавливаем сессию" aria-busy="true" />;
    }

    return isAuthenticated && account.key ? <PartnerDashboard key={account.key} /> : <PartnerLogin />;
};
