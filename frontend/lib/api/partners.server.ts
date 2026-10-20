import 'server-only';
import {cache} from 'react';
import type { PublicPartnerLanding } from '@/lib/partners/types';

import { serverFetch } from '@/lib/server/backend/http';

export const getPublicPartnerLanding = cache(async (
    slug: string,
): Promise<PublicPartnerLanding | null> => {
    const response = await serverFetch(`/partner/landings/${encodeURIComponent(slug)}`, {
        cache: 'no-store',
        signal:AbortSignal.timeout(2000),
    });
    if (response.status === 404) return null;
    if (!response.ok) {
        throw new Error(`Partner landing request failed with status ${response.status}`);
    }
    return response.json() as Promise<PublicPartnerLanding>;
});
