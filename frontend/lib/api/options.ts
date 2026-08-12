import type { VariantOptions } from '@/lib/options/types';

import { request, requestJson } from './http';
import { bearerHeaders } from './headers';

export const getVariantOptions = (signal?: AbortSignal) => requestJson<Partial<VariantOptions>>('/options', {
    signal,
});

export const updateVariantOptions = async (options: VariantOptions, token?: string) => {
    await request('/options', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...bearerHeaders(token) },
        body: JSON.stringify(options),
    });
};
