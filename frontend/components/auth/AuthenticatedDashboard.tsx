import { useState } from 'react';
import Image from 'next/image';

import type { AuthUser, DashboardTab } from '@/lib/auth/types';

import { Text } from '@/components/shared/Text';
import { AuthCloseButton } from './AuthCloseButton';
import { AuthOrdersPanel } from './AuthOrdersPanel';
import { AuthSettingsPanel } from './AuthSettingsPanel';

type AuthenticatedDashboardProps = {
    user: AuthUser | null;
    token: string | null;
    logout: () => void | Promise<void>;
    updateUser: (user: AuthUser) => void;
    onClose: () => void;
};

const DASHBOARD_TAB_LABELS: Record<DashboardTab, string> = {
    profile: 'ПРОФИЛЬ',
    orders: 'ЗАКАЗЫ',
    settings: 'НАСТРОЙКИ',
};

const DashboardNavButton = ({ tab, activeTab, onChange, hasLine }: {
    tab: DashboardTab;
    activeTab: DashboardTab;
    onChange: (tab: DashboardTab) => void;
    hasLine?: boolean;
}) => {
    const isActive = tab === activeTab;
    return (
        <div className="flex flex-col items-start pt-2 pb-2">
            <button
                onClick={() => onChange(tab)}
                className={`font-manrope text-[14px] font-semibold transition-all text-left block w-full ${isActive ? 'text-black' : 'text-[#6F6F6F]'}`}
            >
                {DASHBOARD_TAB_LABELS[tab]}
            </button>
            {hasLine && <div className={`hidden md:block mt-2 mb-2 w-[155px] h-[2px] rounded-[15px] transition-all ${isActive ? 'bg-black' : 'bg-[#F0F0F0]'}`} />}
        </div>
    );
};

const AuthProfilePanel = ({ user }: { user: AuthUser | null }) => (
    <div className="flex flex-col gap-6 h-full">
        <Text size={16} className="text-[#A0A0A0]">Аккаунт: {user?.email}</Text>
        <div className="flex-1 flex flex-col items-center justify-center">
            <div className="relative w-full h-[250px] flex flex-col items-center justify-center text-center overflow-hidden rounded-[20px]">
                <Image src="/login_panel_right.webp" alt="Decor" fill className="object-cover opacity-10 -z-10" />
                <Text size={16} weight="semibold" className="mb-1 text-black">Все возможности сервиса</Text>
                <Text size={16} weight="semibold" className="mb-1 text-black">в нашем приложении</Text>
                <Text size={16} weight="semibold" className="mb-4 text-black">в Телеграмм</Text>
                <Text size={16} weight="semibold" className="text-black">Войти <span className="underline cursor-pointer">здесь</span></Text>
            </div>
        </div>
    </div>
);

export const AuthenticatedDashboard = ({ user, token, logout, updateUser, onClose }: AuthenticatedDashboardProps) => {
    const [activeTab, setActiveTab] = useState<DashboardTab>('profile');

    return (
        <div className="flex flex-col md:flex-row w-full h-[min(700px,calc(100dvh-2rem))] min-h-0 bg-white rounded-[19px] overflow-hidden relative">
            <AuthCloseButton onClick={onClose} />
            <div className="w-full md:w-[230px] flex flex-row md:flex-col flex-wrap items-start justify-start md:justify-center px-4 md:pl-[35px] pt-10 md:pt-0 gap-x-4 md:gap-0 shrink-0">
                <DashboardNavButton tab="profile" activeTab={activeTab} onChange={setActiveTab} hasLine />
                <DashboardNavButton tab="orders" activeTab={activeTab} onChange={setActiveTab} hasLine />
                <DashboardNavButton tab="settings" activeTab={activeTab} onChange={setActiveTab} />
            </div>
            <div className="flex-1 min-w-0 min-h-0 flex flex-col pt-4 md:pt-[50px] px-4 md:pl-[45px] md:pr-10 pb-4 md:pb-[40px] items-start">
                <Text className="text-[24px] md:text-[36px] font-manrope uppercase text-black font-extrabold tracking-tight mb-4 md:mb-[40px]">
                    {DASHBOARD_TAB_LABELS[activeTab]}
                </Text>
                <div className="w-full max-w-[750px] min-h-0 flex-1 bg-[#F7F7F7] rounded-[15px] p-3 md:p-5 overflow-y-auto scrollbar-hide">
                    {activeTab === 'profile' && <AuthProfilePanel user={user} />}
                    {activeTab === 'orders' && <AuthOrdersPanel />}
                    {activeTab === 'settings' && (
                        <AuthSettingsPanel user={user} token={token} updateUser={updateUser} logout={logout} />
                    )}
                </div>
            </div>
        </div>
    );
};
