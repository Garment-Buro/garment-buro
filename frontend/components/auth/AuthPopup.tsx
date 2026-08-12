"use client";

import { AuthenticationPanel } from '@/components/auth/AuthenticationPanel';
import { AuthenticatedDashboard } from '@/components/auth/AuthenticatedDashboard';
import { useAuthStore } from '@/store/authStore';

import { Popup } from '@/components/shared/Popup';

interface AuthPopupProps {
    isOpen: boolean;
    onClose: () => void;
}

export const AuthPopup = ({ isOpen, onClose }: AuthPopupProps) => {
    const auth = useAuthStore();
    if (!isOpen) return null;

    return (
        <Popup onClose={onClose} showClose={false} maxWidth={auth.isAuthenticated ? 1200 : 975}>
            {!auth.isSessionReady ? (
                <div className="w-full h-[300px] flex items-center justify-center bg-white rounded-[19px]">
                    <span className="font-manrope text-[16px] text-[#898989]">Восстанавливаем сессию…</span>
                </div>
            ) : auth.isAuthenticated ? (
                <AuthenticatedDashboard
                    user={auth.user}
                    token={auth.token}
                    logout={auth.logout}
                    updateUser={auth.updateUser}
                    onClose={onClose}
                />
            ) : (
                <AuthenticationPanel onClose={onClose} setAuth={auth.setAuth} />
            )}
        </Popup>
    );
};
