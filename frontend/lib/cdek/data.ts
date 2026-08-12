import type { CdekOffice, CityPreset, TariffResult } from '@/lib/cdek/types';

export const CITY_PRESETS: CityPreset[] = [
    { label: 'Москва', code: 44 },
    { label: 'Санкт-Петербург', code: 137 },
    { label: 'Тверь', code: 245 },
];

export const DEMO_TARIFF: TariffResult = {
    delivery_sum: 390,
    period_min: 2,
    period_max: 4,
    tariff_name: 'Демо тариф склад-склад',
};

export const DEMO_OFFICES: CdekOffice[] = [
    {
        code: 'DEMO-MSK-1',
        name: 'Демо ПВЗ на Патриарших',
        type: 'PVZ',
        work_time: 'Пн-Вс 10:00-21:00',
        nearest_station: 'Маяковская',
        phones: [{ number: '+7 900 000-00-01' }],
        location: {
            city: 'Москва', address: 'Большая Садовая, 10',
            address_full: 'Москва, Большая Садовая, 10', latitude: 55.7671, longitude: 37.5935,
        },
    },
    {
        code: 'DEMO-MSK-2',
        name: 'Демо ПВЗ Китай-город',
        type: 'PVZ',
        work_time: 'Пн-Пт 09:00-20:00, Сб-Вс 10:00-18:00',
        nearest_station: 'Китай-город',
        phones: [{ number: '+7 900 000-00-02' }],
        location: {
            city: 'Москва', address: 'Маросейка, 7/8',
            address_full: 'Москва, Маросейка, 7/8', latitude: 55.7574, longitude: 37.6358,
        },
    },
    {
        code: 'DEMO-MSK-3',
        name: 'Демо ПВЗ Замоскворечье',
        type: 'PVZ',
        work_time: 'Ежедневно 10:00-22:00',
        nearest_station: 'Третьяковская',
        phones: [{ number: '+7 900 000-00-03' }],
        location: {
            city: 'Москва', address: 'Пятницкая, 29',
            address_full: 'Москва, Пятницкая, 29', latitude: 55.7406, longitude: 37.6275,
        },
    },
];
