import { isCatalogWritesV2Enabled } from '@/lib/auth/config';
import { useAuthStore } from '@/store/authStore';

export const runCatalogWrite = <Result>(
    operation: (token?: string) => Promise<Result>,
): Promise<Result> => {
    if (!isCatalogWritesV2Enabled()) return operation();
    return useAuthStore.getState().runAuthenticated(token => operation(token));
};
