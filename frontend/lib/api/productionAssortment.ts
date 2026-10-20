import { requestJson, requestReadJson } from '@/lib/api/http';
import { useProductionAuthStore } from '@/store/productionAuthStore';

const root = '/production/admin/assortment';

export const assortmentRequest = <T>(path: string, init?: RequestInit) =>
    useProductionAuthStore.getState().runAuthenticated(() => requestJson<T>(`${root}/${path.replace(/^\//, '')}`, {
        cache: 'no-store',
        ...init,
    }));

export const readAssortment = <T>(path: string, signal?: AbortSignal) =>
    useProductionAuthStore.getState().runAuthenticated(() =>
        requestReadJson<T>(`${root}/${path.replace(/^\//, '')}`, {signal, cache: 'no-store'}));

export const saveAssortment = <T>(
    path: string,
    method: 'POST' | 'PUT',
    payload: unknown,
) =>
    assortmentRequest<T>(path, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });

export const uploadAssortmentMedia = async (
    file: File,
    kind: 'public' | 'pattern',
) => {
    const body = new FormData();
    body.append('file', file);
    return assortmentRequest<{ id: number; url?: string; filename?: string }>(
        `media/${kind}`,
        { method: 'POST', body },
    );
};

