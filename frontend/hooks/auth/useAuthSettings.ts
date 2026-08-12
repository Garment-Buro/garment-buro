import { useState } from 'react';

import { deleteAuthProfile, updateAuthProfile } from '@/lib/api/auth';
import type { AuthProfileData, AuthUser } from '@/lib/auth/types';
import { createAuthProfileData, hasUsableAuthToken } from '@/lib/auth/utils/auth';
import { useAuthStore } from '@/store/authStore';

type UseAuthSettingsOptions = {
    user: AuthUser | null;
    token: string | null;
    updateUser: (user: AuthUser) => void;
    logout: () => void | Promise<void>;
};

export const useAuthSettings = ({ user, token, updateUser, logout }: UseAuthSettingsOptions) => {
    const [profile, setProfile] = useState<AuthProfileData>(() => createAuthProfileData(user));
    const [saving, setSaving] = useState(false);
    const runAuthenticated = useAuthStore(state => state.runAuthenticated);

    const setProfileField = <Field extends keyof AuthProfileData>(field: Field, value: AuthProfileData[Field]) => {
        setProfile(currentProfile => ({ ...currentProfile, [field]: value }));
    };

    const saveProfile = async () => {
        if (!hasUsableAuthToken(token)) return;
        setSaving(true);
        try {
            updateUser(await runAuthenticated(
                authToken => updateAuthProfile(authToken, profile),
            ));
        } finally {
            setSaving(false);
        }
    };

    const removeProfile = async () => {
        if (!hasUsableAuthToken(token) || !window.confirm('Вы уверены?')) return;
        await runAuthenticated(authToken => deleteAuthProfile(authToken));
        await logout();
    };

    return { profile, setProfileField, saving, saveProfile, removeProfile };
};
