'use client';

import { useCallback, useEffect, useState } from 'react';
import { assortmentRequest } from '@/lib/api/productionAssortment';

export function useAssortmentResource<T>(path: string) {
    const [data, setData] = useState<T | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [revision, setRevision] = useState(0);
    const reload = useCallback(() => setRevision((value) => value + 1), []);

    useEffect(() => {
        const controller = new AbortController();
        void (async () => {
            setLoading(true);
            setError('');
            try {
                const value = await assortmentRequest<T>(path, {
                    signal: controller.signal,
                });
                if (!controller.signal.aborted) setData(value);
            } catch (reason) {
                if (!controller.signal.aborted) {
                    setError(
                        reason instanceof Error
                            ? reason.message
                            : 'Не удалось загрузить данные',
                    );
                }
            } finally {
                if (!controller.signal.aborted) setLoading(false);
            }
        })();
        return () => controller.abort();
    }, [path, revision]);

    return { data, loading, error, reload };
}
