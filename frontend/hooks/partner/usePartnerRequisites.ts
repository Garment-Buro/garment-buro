'use client';

import { useEffect, useState, useSyncExternalStore } from 'react';
import { RequisitesEditor } from '@/lib/partners/requisitesEditor';
import { getPartnerRequisites, updatePartnerRequisites } from '@/lib/api/partners';
import { useCustomerAccount, runForCustomer, isCustomerSessionCurrent } from '@/hooks/catalog/customerSession';

export function usePartnerRequisites(active: boolean, onSaved?: () => void) {
    const { key, userId } = useCustomerAccount();
    const [editor] = useState(() => new RequisitesEditor());
    const state = useSyncExternalStore(editor.subscribe, editor.getSnapshot, editor.getSnapshot);
    useEffect(() => {
        editor.setAccount(key, key !== null && userId !== null ? {
            read: signal => runForCustomer(userId, token => getPartnerRequisites(token, signal), key),
            save: (draft, signal) => runForCustomer(userId, token => updatePartnerRequisites(token, draft, signal), key),
        } : null);
        return editor.dispose;
    }, [editor, key, userId]);
    useEffect(() => {
        if (active) void editor.load(); else editor.cancelRead();
    }, [active, editor, key]);
    const canAct = () => key !== null && userId !== null && editor.getSnapshot().account === key && isCustomerSessionCurrent(userId, key);
    return {
        state: key !== null && state.account === key ? state : null,
        retry: () => canAct() ? editor.load() : Promise.resolve(false),
        reload: () => canAct() ? editor.reload() : Promise.resolve(false),
        setField: ((...args: Parameters<typeof editor.setField>) => { if (canAct()) editor.setField(...args); }) as typeof editor.setField,
        setEntityType: (value: Parameters<typeof editor.setEntityType>[0]) => { if (canAct()) editor.setEntityType(value); },
        save: async () => {
            if (!canAct()) return false;
            const saved = await editor.save();
            if (saved && canAct()) onSaved?.();
            return saved;
        },
    };
}
