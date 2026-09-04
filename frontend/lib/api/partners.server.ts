import type { PublicPartnerLanding } from '@/lib/partners/types';

import { serverFetch } from '@/lib/server/backend/http';

export const getPublicPartnerLanding = async (
    slug: string,
): Promise<PublicPartnerLanding | null> => {
    const response = await serverFetch(`/partner/landings/${encodeURIComponent(slug)}`, {
        next: { revalidate: 60 },
    });
    if (response.status === 404) return null;
    if (!response.ok) {
        throw new Error(`Partner landing request failed with status ${response.status}`);
    }
    return response.json() as Promise<PublicPartnerLanding>;
};
