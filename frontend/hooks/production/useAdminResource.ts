'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { requestJson } from '@/lib/api/http';
import { useProductionAuthStore } from '@/store/productionAuthStore';

export function useAdminResource<T>(path: string, refreshIntervalMs = 0) {
    const epoch = useProductionAuthStore(state => state.sessionEpoch);
    const resourceKey = `${epoch}:${path}`;
    const run = useProductionAuthStore((state) => state.runAuthenticated);
    const [result, setResult] = useState<{
        path: string;
        data: T | null;
        error: string;
    }>({ path: '', data: null, error: '' });
    const resultRef = useRef(result);
    resultRef.current = result;
    const [loading, setLoading] = useState(true);
    const [revision, setRevision] = useState(0);
    const reload = useCallback(() => setRevision((value) => value + 1), []);
    useEffect(() => {
        const controller = new AbortController();
        const hasCurrentData =
            resultRef.current.path === resourceKey &&
            resultRef.current.data !== null;
        void (async () => {
            if (!hasCurrentData) {
                setLoading(true);
                setResult({ path: resourceKey, data: null, error: '' });
            } else {
                setResult((current) => ({ ...current, error: '' }));
            }
            try {
                const data = await run(() =>
                    requestJson<T>(`/production/admin/${path}`, {
                        cache: 'no-store',
                        signal: controller.signal,
                    }),
                );
                if (!controller.signal.aborted)
                    setResult({ path: resourceKey, data, error: '' });
            } catch (error) {
                if (!controller.signal.aborted)
                    setResult({
                        path: resourceKey,
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
    }, [path, resourceKey, revision, run]);
    useEffect(() => {
        if (refreshIntervalMs <= 0) return;
        const refreshWhenVisible = () => {
            if (document.visibilityState === 'visible') reload();
        };
        const timer = window.setInterval(
            refreshWhenVisible,
            refreshIntervalMs,
        );
        document.addEventListener('visibilitychange', refreshWhenVisible);
        return () => {
            window.clearInterval(timer);
            document.removeEventListener(
                'visibilitychange',
                refreshWhenVisible,
            );
        };
    }, [refreshIntervalMs, reload]);
    return {
        data: result.path === resourceKey ? result.data : null,
        error: result.path === resourceKey ? result.error : '',
        loading: loading || result.path !== resourceKey,
        reload,
    };
}
