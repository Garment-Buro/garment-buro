import type { AddressSuggestion, CdekOffice, TariffResult } from '@/lib/cdek/types';
import { pickCdekTariff } from '@/lib/cdek/utils/cdek';

import { requestJson } from './http';

export const getAddressSuggestions = (query: string, city: string, signal?: AbortSignal) => (
    requestJson<AddressSuggestion[]>(
        `/address-suggest?q=${encodeURIComponent(query)}&city=${encodeURIComponent(city)}`,
        { signal },
    )
);

export const getCdekOffices = async (cityCode: number, signal?: AbortSignal) => {
    const params = new URLSearchParams({
        action: 'offices', city_code: String(cityCode), type: 'PVZ', country_code: 'RU',
    });
    const offices = await requestJson<CdekOffice[]>(`/cdek-service?${params}`, {
        signal,
        headers: { Accept: 'application/json' },
    });
    if (!offices.length) throw new Error('CDEK returned an empty office list');
    return offices;
};

export const calculateCdekDelivery = async (cityCode: number, signal?: AbortSignal): Promise<TariffResult> => {
    const data = await requestJson<unknown>('/cdek-service?action=calculate', {
        method: 'POST',
        signal,
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
            type: 1,
            currency: 1,
            tariff_codes: [{ tariff_code: 136 }],
            from_location: { code: 245 },
            to_location: { code: cityCode },
            packages: [{ weight: 1000, length: 20, width: 20, height: 10 }],
        }),
    });
    const tariff = pickCdekTariff(data);
    if (!tariff?.delivery_sum) throw new Error('No tariff in CDEK response');
    return tariff;
};
