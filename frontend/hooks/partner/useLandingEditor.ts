'use client';

import { useEffect, useState, useSyncExternalStore } from 'react';
import {
    createOwnLanding,
    getOwnLanding,
    getOwnLandings,
    updateOwnLanding,
} from '@/lib/api/partnerLandings';
import { LandingEditor, landingDirty } from '@/lib/partners/landingEditor';
import {
    isCustomerSessionCurrent,
    runForCustomer,
    useCustomerAccount,
} from '@/hooks/catalog/customerSession';

export function useLandingEditor() {
    const { key, userId } = useCustomerAccount();
    const [editor] = useState(() => new LandingEditor());
    const snapshot = useSyncExternalStore(editor.subscribe, editor.getSnapshot, editor.getSnapshot);
    useEffect(() => {
        void editor.setAccount(
            key,
            key !== null && userId !== null
                ? {
                      list: (cursor, signal) =>
                          runForCustomer(
                              userId,
                              (token) => getOwnLandings(token, cursor, signal),
                              key,
                          ),
                      load: (id, signal) =>
                          runForCustomer(userId, (token) => getOwnLanding(token, id, signal), key),
                      create: (value, signal) =>
                          runForCustomer(
                              userId,
                              (token) => createOwnLanding(token, value, signal),
                              key,
                          ),
                      update: (id, value, signal) =>
                          runForCustomer(
                              userId,
                              (token) => updateOwnLanding(token, id, value, signal),
                              key,
                          ),
                  }
                : null,
        );
        return editor.dispose;
    }, [editor, key, userId]);
    const canAct = () =>
        key !== null &&
        userId !== null &&
        editor.getSnapshot().account === key &&
        isCustomerSessionCurrent(userId, key);
    return {
        state: key !== null && snapshot.account === key ? snapshot : null,
        dirty: landingDirty(snapshot),
        setField: ((...args: Parameters<typeof editor.setField>) => {
            if (canAct()) editor.setField(...args);
        }) as typeof editor.setField,
        setProducts: (ids: number[]) => {
            if (canAct()) editor.setProducts(ids);
        },
        createDraft: () => {
            if (canAct()) editor.createDraft();
        },
        close: () => {
            if (canAct()) editor.close();
        },
        open: (id: number) => (canAct() ? editor.open(id) : Promise.resolve(false)),
        save: () => (canAct() ? editor.save() : Promise.resolve(false)),
        publish: (value: boolean) => (canAct() ? editor.publish(value) : Promise.resolve(false)),
        reload: () => (canAct() ? editor.reload() : Promise.resolve(false)),
        more: () => (canAct() ? editor.more() : Promise.resolve(false)),
        retryList: () => (canAct() ? editor.loadList() : Promise.resolve(false)),
    };
}
