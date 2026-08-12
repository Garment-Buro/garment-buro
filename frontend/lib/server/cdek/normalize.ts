import type { CdekOffice, TariffResult } from '@/lib/cdek/types';

type UnknownRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is UnknownRecord => (
    value !== null && typeof value === 'object' && !Array.isArray(value)
);

const readString = (value: unknown) => (
    typeof value === 'string' && value.trim() ? value : undefined
);

const readNumber = (value: unknown) => (
    typeof value === 'number' && Number.isFinite(value) ? value : undefined
);

const normalizeLocation = (value: unknown): CdekOffice['location'] | undefined => {
    if (!isRecord(value)) return undefined;

    const location = {
        city: readString(value.city),
        address: readString(value.address),
        address_full: readString(value.address_full),
        latitude: readNumber(value.latitude),
        longitude: readNumber(value.longitude),
    };

    return Object.values(location).some((item) => item !== undefined)
        ? location
        : undefined;
};

const normalizePhones = (value: unknown): CdekOffice['phones'] | undefined => {
    if (!Array.isArray(value)) return undefined;

    const phones = value.flatMap((candidate) => {
        if (!isRecord(candidate)) return [];
        const number = readString(candidate.number);
        return number ? [{ number }] : [];
    });

    return phones.length ? phones : undefined;
};

export const normalizeCdekOffices = (value: unknown): CdekOffice[] => {
    if (!Array.isArray(value)) return [];

    return value.flatMap((candidate) => {
        if (!isRecord(candidate)) return [];
        const code = readString(candidate.code);
        if (!code) return [];

        return [{
            code,
            name: readString(candidate.name),
            type: readString(candidate.type),
            owner_code: readString(candidate.owner_code),
            work_time: readString(candidate.work_time),
            nearest_station: readString(candidate.nearest_station),
            note: readString(candidate.note),
            phones: normalizePhones(candidate.phones),
            location: normalizeLocation(candidate.location),
        }];
    });
};

const normalizeTariff = (value: unknown): TariffResult | null => {
    if (!isRecord(value)) return null;
    const deliverySum = readNumber(value.delivery_sum);
    if (deliverySum === undefined) return null;

    return {
        delivery_sum: deliverySum,
        period_min: readNumber(value.period_min),
        period_max: readNumber(value.period_max),
        tariff_name: readString(value.tariff_name),
    };
};

export const normalizeCdekTariffs = (value: unknown): { tariff_codes: TariffResult[] } => {
    if (!isRecord(value)) return { tariff_codes: [] };

    const candidates = Array.isArray(value.tariff_codes)
        ? value.tariff_codes
        : [value];
    return {
        tariff_codes: candidates.flatMap((candidate) => {
            const tariff = normalizeTariff(candidate);
            return tariff ? [tariff] : [];
        }),
    };
};
