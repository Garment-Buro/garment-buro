import type { AddressSuggestion } from '@/lib/location/types';

import { buildAddressSearchParams, normalizeAddressSuggestions } from './utils';

const GEOCODING_API_URL = process.env.GEOCODING_API_URL
    || 'https://nominatim.openstreetmap.org/search';
const GEOCODING_USER_AGENT = process.env.GEOCODING_USER_AGENT
    || 'garment-buro-address-suggest/1.0 info@garment-buro.ru';
const GEOCODING_CACHE_SECONDS = 60 * 60 * 24;
const GEOCODING_TIMEOUT_MS = 5_000;

export const getAddressSuggestions = async (
    query: string,
    city: string,
): Promise<AddressSuggestion[]> => {
    const searchParams = buildAddressSearchParams(query, city);
    const response = await fetch(`${GEOCODING_API_URL}?${searchParams.toString()}`, {
        headers: {
            Accept: 'application/json',
            'User-Agent': GEOCODING_USER_AGENT,
        },
        next: { revalidate: GEOCODING_CACHE_SECONDS },
        signal: AbortSignal.timeout(GEOCODING_TIMEOUT_MS),
    });

    if (!response.ok) {
        throw new Error(`Geocoding service returned ${response.status}`);
    }

    return normalizeAddressSuggestions(await response.json(), query);
};
