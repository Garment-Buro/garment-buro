import { useEffect, useState, useSyncExternalStore } from 'react';

import { deleteAuthProfile, updateAuthProfile } from '@/lib/api/auth';
import type { AuthProfileData, AuthUser } from '@/lib/auth/types';
import { createAuthProfileData } from '@/lib/auth/utils/auth';
import { ProfileEditor } from '@/lib/auth/profileEditor';
import { useAuthStore } from '@/store/authStore';
import { isCustomerSessionCurrent, runForCustomer, useCustomerAccount } from '@/hooks/catalog/customerSession';

type UseAuthSettingsOptions = {
    user: AuthUser | null;
    updateUser: (user: AuthUser) => void;
    logout: () => void | Promise<void>;
};

export const useAuthSettings = ({ user, updateUser, logout }: UseAuthSettingsOptions) => {
    const session = useCustomerAccount();
    const account = user?.id === session.userId ? session.key : null;
    const userId = account === null ? null : session.userId;
    const [editor] = useState(() => new ProfileEditor());
    const [confirmedAccount, setConfirmedAccount] = useState<string | null>(null);
    const snapshot = useSyncExternalStore(editor.subscribe, editor.getSnapshot, editor.getSnapshot);
    useEffect(() => {
        const owner = userId === null ? null : useAuthStore.getState().user;
        const belongsToAccount = () => userId !== null && isCustomerSessionCurrent(userId, account);
        editor.setAccount(account, owner, userId !== null && account !== null ? {
            save: (profile, signal) => runForCustomer(userId, authToken => updateAuthProfile(authToken, profile, signal), account),
            remove: signal => runForCustomer(userId, authToken => deleteAuthProfile(authToken, signal), account),
            confirm: updated => {
                if (belongsToAccount()) {
                    setConfirmedAccount(account);
                    updateUser(updated);
                }
            },
            logout: () => { if (belongsToAccount()) return logout(); },
        } : null);
        return editor.dispose;
    }, [account, userId, updateUser, logout, editor]);

    const current = account !== null && snapshot.account === account;
    const canEdit = () => userId !== null && editor.getSnapshot().account === account
        && isCustomerSessionCurrent(userId, account);
    return {
        profile: current ? snapshot.profile : createAuthProfileData(userId === null ? null : user),
        setProfileField: <Field extends keyof AuthProfileData>(field: Field, value: AuthProfileData[Field]) => {
            if (!canEdit()) return;
            setConfirmedAccount(null);
            editor.setField(field, value);
        },
        saving: current && snapshot.status === 'saving',
        deleting: current && snapshot.status === 'deleting',
        saved: current && confirmedAccount === account,
        error: current ? snapshot.error : null,
        saveProfile: () => canEdit() ? editor.save() : Promise.resolve(false),
        removeProfile: async () => {
            if (canEdit() && window.confirm('Удалить аккаунт без возможности восстановления?') && canEdit()) await editor.remove();
        },
    };
};
