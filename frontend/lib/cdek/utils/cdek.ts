import type { CdekOffice, Coordinates } from '@/lib/cdek/types';

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
