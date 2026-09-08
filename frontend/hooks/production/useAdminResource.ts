'use client';

import { useCallback, useEffect, useState } from 'react';
import { requestJson } from '@/lib/api/http';
import { useProductionAuthStore } from '@/store/productionAuthStore';

export function useAdminResource<T>(path: string) {
    const run = useProductionAuthStore((state) => state.runAuthenticated);
    const [result, setResult] = useState<{
        path: string;
        data: T | null;
        error: string;
    }>({ path: '', data: null, error: '' });
    const [loading, setLoading] = useState(true);
    const [revision, setRevision] = useState(0);
    const reload = useCallback(() => setRevision((value) => value + 1), []);
    useEffect(() => {
        const controller = new AbortController();
        void (async () => {
            setLoading(true);
            setResult({ path, data: null, error: '' });
            try {
                const data = await run(() =>
                    requestJson<T>(`/production/admin/${path}`, {
                        cache: 'no-store',
                        signal: controller.signal,
                    }),
                );
                if (!controller.signal.aborted)
                    setResult({ path, data, error: '' });
            } catch (error) {
                if (!controller.signal.aborted)
                    setResult({
                        path,
                        data: null,
                        error:
                            error instanceof Error
                                ? error.message
                                : 'Не удалось загрузить данные',
                    });
            } finally {
                if (!controller.signal.aborted) setLoading(false);
            }
        })();
        return () => controller.abort();
    }, [path, revision, run]);
    return {
        data: result.path === path ? result.data : null,
        error: result.path === path ? result.error : '',
        loading: loading || result.path !== path,
        reload,
    };
}
