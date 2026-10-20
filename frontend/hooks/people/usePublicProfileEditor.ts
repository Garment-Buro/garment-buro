'use client';

import { useEffect, useState, useSyncExternalStore } from 'react';
import { getOwnPublicProfile, savePublicProfile, uploadProfileAvatar, removeProfileAvatar, readOwnProfileAvatar } from '@/lib/api/people';
import { PublicProfileEditor, hasPublicProfileChanges } from '@/lib/people/publicProfileEditor';
import { useCustomerAccount, runForCustomer, isCustomerSessionCurrent } from '@/hooks/catalog/customerSession';

export function usePublicProfileEditor() {
    const { key, userId, sessionReady } = useCustomerAccount();
    const [editor] = useState(() => new PublicProfileEditor());
    const snapshot = useSyncExternalStore(editor.subscribe, editor.getSnapshot, editor.getSnapshot);
    useEffect(() => {
        void editor.setAccount(key, key !== null && userId !== null ? {
            load: signal => runForCustomer(userId, token => getOwnPublicProfile(token, signal), key),
            save: (value, signal) => runForCustomer(userId, token => savePublicProfile(token, value, signal), key),
            upload: (version, file, signal) => runForCustomer(userId, token => uploadProfileAvatar(token, version, file, signal), key),
            remove: (version, signal) => runForCustomer(userId, token => removeProfileAvatar(token, version, signal), key),
            preview: (id, signal) => runForCustomer(userId, token => readOwnProfileAvatar(token, id, signal), key),
        } : null);
        return editor.dispose;
    }, [editor, key, userId]);
    const current = key !== null && snapshot.account === key;
    const canAct = () => userId !== null && key !== null && editor.getSnapshot().account === key && isCustomerSessionCurrent(userId, key);
    return {
        sessionReady, authenticated: key !== null,
        state: current ? snapshot : null,
        dirty: current && hasPublicProfileChanges(snapshot),
        setField: (field: 'slug' | 'display_name' | 'bio', value: string) => { if (canAct()) editor.setField(field, value); },
        save: () => canAct() ? editor.save() : Promise.resolve(false),
        publish: (value: boolean) => canAct() ? editor.setPublished(value) : Promise.resolve(false),
        reload: () => canAct() ? editor.reload() : Promise.resolve(false),
        upload: (file: File) => canAct() ? editor.upload(file) : Promise.resolve(false),
        removeAvatar: () => canAct() ? editor.removeAvatar() : Promise.resolve(false),
    };
}
