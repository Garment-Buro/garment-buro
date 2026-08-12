import type { CdekOffice, Coordinates, TariffResult } from '@/lib/cdek/types';

export const formatCdekPrice = (value: number) => new Intl.NumberFormat('ru-RU').format(value);

export const getOfficeTitle = (office: CdekOffice) => office.name || office.code;

export const getOfficeAddress = (office: CdekOffice) => (
    office.location?.address_full || office.location?.address || 'Адрес не указан'
);

export const getOfficeCoords = (office: CdekOffice): Coordinates | null => {
    const latitude = office.location?.latitude;
    const longitude = office.location?.longitude;
    return typeof latitude === 'number' && typeof longitude === 'number'
        ? [latitude, longitude]
        : null;
};

export const getDistanceKm = (from: Coordinates, to: Coordinates) => {
    const earthRadiusKm = 6371;
    const toRadians = (value: number) => value * Math.PI / 180;
    const latitudeDelta = toRadians(to[0] - from[0]);
    const longitudeDelta = toRadians(to[1] - from[1]);
    const latitude1 = toRadians(from[0]);
    const latitude2 = toRadians(to[0]);
    const haversine = Math.sin(latitudeDelta / 2) ** 2
        + Math.cos(latitude1) * Math.cos(latitude2) * Math.sin(longitudeDelta / 2) ** 2;
    return earthRadiusKm * 2 * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
};

export const filterCdekOffices = (
    offices: CdekOffice[],
    query: string,
    searchCenter: Coordinates | null,
) => {
    if (searchCenter) {
        return offices
            .map((office) => ({
                office,
                distance: getOfficeCoords(office)
                    ? getDistanceKm(searchCenter, getOfficeCoords(office) as Coordinates)
                    : Number.POSITIVE_INFINITY,
            }))
            .sort((left, right) => left.distance - right.distance)
            .map(({ office }) => office)
            .slice(0, 80);
    }

    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return offices.slice(0, 80);

    return offices.filter((office) => [
        office.code,
        office.name,
        office.type,
        office.work_time,
        office.nearest_station,
        office.location?.city,
        office.location?.address,
        office.location?.address_full,
    ].filter(Boolean).join(' ').toLowerCase().includes(normalizedQuery)).slice(0, 80);
};

export const pickCdekTariff = (data: unknown): TariffResult | null => {
    if (!data || typeof data !== 'object') return null;
    const response = data as { tariff_codes?: TariffResult[] } & TariffResult;
    if (response.tariff_codes?.length) return response.tariff_codes[0];
    return typeof response.delivery_sum === 'number' ? response : null;
};

export const getAddressSuggestionLabel = (suggestion: { displayName?: string; value?: string }) => (
    suggestion.displayName || suggestion.value || ''
);

export const sanitizeCdekCityCode = (value: string) => value.replace(/[^0-9]/g, '');
