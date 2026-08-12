import type { AddressSuggestion } from '@/lib/location/types';

type GeocodingRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is GeocodingRecord => (
    value !== null && typeof value === 'object' && !Array.isArray(value)
);

const readLabel = (item: GeocodingRecord, fallback: string) => {
    const displayName = item.display_name;
    if (typeof displayName === 'string' && displayName.trim()) return displayName;

    const name = item.name;
    if (typeof name === 'string' && name.trim()) return name;

    return fallback;
};

export const buildAddressSearchParams = (query: string, city: string) => new URLSearchParams({
    format: 'jsonv2',
    addressdetails: '1',
    countrycodes: 'ru',
    limit: '6',
    q: city && !query.toLowerCase().includes(city.toLowerCase()) ? `${query}, ${city}` : query,
});

export const normalizeAddressSuggestions = (
    value: unknown,
    fallbackLabel: string,
): AddressSuggestion[] => {
    if (!Array.isArray(value)) return [];

    return value.flatMap((candidate) => {
        if (!isRecord(candidate)) return [];

        const latitude = Number(candidate.lat);
        const longitude = Number(candidate.lon);
        if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return [];

        const label = readLabel(candidate, fallbackLabel);
        return [{
            value: label,
            displayName: label,
            coords: [latitude, longitude],
        }];
    });
};
