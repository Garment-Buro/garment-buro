'use client';

import { useEffect, useState, useSyncExternalStore } from 'react';
import { useAuthStore } from '@/store/authStore';
import { importDesignImages, uploadDesignImage } from '@/lib/api/designMedia';
import { ConstructorCartPreparation } from '@/lib/constructor/cartPreparation';

const getScope = () => {
    const state = useAuthStore.getState();
    if (!state.isSessionReady || state.sessionRestorePending || state.logoutPending) return null;
    if (state.isAuthenticated) return state.user?.id && state.token ? `${state.user.id}:${state.accountEpoch}` : null;
    return 'guest';
};

export function useConstructorCartPreparation() {
    const [preparation] = useState(() => new ConstructorCartPreparation({
        origin: typeof window === 'undefined' ? '' : window.location.origin,
        getScope,
        upload: uploadDesignImage,
        import: (ids, signal) => {
            const scope = getScope();
            if (scope === null || scope === 'guest') throw new Error('Войдите в аккаунт владельца, чтобы использовать изображения проекта.');
            return useAuthStore.getState().runAuthenticated(token => {
                signal.throwIfAborted();
                if (getScope() !== scope) throw new DOMException('Account changed', 'AbortError');
                return importDesignImages(ids, token, signal);
            });
        },
    }));
    const isPreparing = useSyncExternalStore(preparation.subscribe, preparation.getSnapshot, () => false);
    useEffect(() => {
        let scope = getScope();
        const unsubscribe = useAuthStore.subscribe(() => {
            const current = getScope();
            if (current !== scope) { scope = current; preparation.reset(); }
        });
        return () => { unsubscribe(); preparation.reset(); };
    }, [preparation]);
    return { isPreparing, cancel: preparation.cancel, submit: preparation.submit.bind(preparation) };
}
