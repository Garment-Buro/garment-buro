import { isCatalogWritesV2Enabled } from '@/lib/auth/config';
import { useAuthStore } from '@/store/authStore';

/** Administrative reads and writes share session refresh; no anonymous fallback. */
export const runCatalogRequest = async <Result>(
    operation: (token: string) => Promise<Result>,
): Promise<Result> => {
    if (!isCatalogWritesV2Enabled()) throw new Error('Управление каталогом отключено.');
    return useAuthStore.getState().runAuthenticated(async token => {
        const before = useAuthStore.getState();
        const userId = before.user?.id;
        const epoch = before.accountEpoch;
        if (!userId) throw new DOMException('Session changed', 'AbortError');
        const value = await operation(token);
        const current = useAuthStore.getState();
        if (current.user?.id !== userId || current.accountEpoch !== epoch) {
            throw new DOMException('Session changed', 'AbortError');
        }
        return value;
    });
};
