import { useEffect, useState } from 'react';
import { requestJson } from '@/lib/api/http';
import type { CdekOffice } from '@/lib/cdek/types';

type DirectoryPage = { points: CdekOffice[]; total: number; updated_at: string; stale: boolean };
export function usePickupDirectory(query: string, offset: number, enabled: boolean) {
    const [page, setPage] = useState<DirectoryPage | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [attempt, setAttempt] = useState(0);
    useEffect(() => {
        if (!enabled) return;
        const abort = new AbortController();
        const timer = setTimeout(async () => {
            setLoading(true); setError('');
            try {
                const params = new URLSearchParams({ q: query.trim(), offset: String(offset), limit: '50' });
                const result = await requestJson<DirectoryPage>(`/cdek/points?${params}`, { signal: abort.signal });
                if (!abort.signal.aborted) setPage(result);
            } catch {
                if (!abort.signal.aborted) { setPage(null); setError('Не удалось загрузить пункты СДЭК. Попробуйте ещё раз позже.'); }
            } finally {
                if (!abort.signal.aborted) setLoading(false);
            }
        }, 300);
        return () => { clearTimeout(timer); abort.abort(); };
    }, [query, offset, attempt, enabled]);
    return { page, loading, error, retry: () => setAttempt(value => value + 1) };
}
