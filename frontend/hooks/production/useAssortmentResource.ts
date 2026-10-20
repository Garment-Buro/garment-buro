'use client';

import { useCallback, useEffect, useState } from 'react';
import { readAssortment } from '@/lib/api/productionAssortment';
import { useProductionAuthStore } from '@/store/productionAuthStore';

/** One account lifetime and one path own this read; old data is hidden immediately. */
export function useAssortmentResource<T>(
    path: string,
    enabled = true,
    decode?: (value: unknown) => T,
    refreshKey = 0,
) {
    const epoch = useProductionAuthStore((state) => state.sessionEpoch);
    const authenticated = useProductionAuthStore(
        (state) => state.isAuthenticated,
    );
    const active = enabled && authenticated && epoch !== null;
    const key = `${epoch}:${path}:${refreshKey}`;
    const [result, setResult] = useState<{
        key: string;
        data: T | null;
        error: string;
        loading: boolean;
    }>({ key: '', data: null, error: '', loading: false });
    const [revision, setRevision] = useState(0);
    const reload = useCallback(() => setRevision((value) => value + 1), []);
    useEffect(() => {
        if (!active) return;
        const controller = new AbortController();
        void (async () => {
            await Promise.resolve();
            if (controller.signal.aborted) return;
            setResult((current) => ({
                key,
                data: current.key === key ? current.data : null,
                error: '',
                loading: true,
            }));
            try {
                const raw = await readAssortment<unknown>(
                    path,
                    controller.signal,
                );
                const data = decode ? decode(raw) : (raw as T);
                if (!controller.signal.aborted)
                    setResult({ key, data, error: '', loading: false });
            } catch (error) {
                if (!controller.signal.aborted)
                    setResult((current) => ({
                        key,
                        data: current.key === key ? current.data : null,
                        loading: false,
                        error:
                            error instanceof Error
                                ? error.message
                                : 'Не удалось загрузить данные',
                    }));
            }
        })();
        return () => controller.abort();
    }, [path, key, revision, active, decode]);
    const current = active && result.key === key;
    return {
        data: current ? result.data : null,
        error: current ? result.error : '',
        loading: active && (!current || result.loading),
        reload,
    };
}
