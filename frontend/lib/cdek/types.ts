import type { Coordinates } from '@/lib/location/types';

export type { AddressSuggestion, Coordinates } from '@/lib/location/types';

export type LoadState = 'idle' | 'loading' | 'ready' | 'error';

export type CdekOffice = {
    code: string;
    name?: string;
    type?: string;
    owner_code?: string;
    work_time?: string;
    nearest_station?: string;
    note?: string;
    phones?: Array<{ number?: string }>;
    location?: {
        city?: string;
        address?: string;
        address_full?: string;
        latitude?: number;
        longitude?: number;
    };
};

export type TariffResult = {
    delivery_sum?: number;
    period_min?: number;
    period_max?: number;
    tariff_name?: string;
};

export type CityPreset = {
    label: string;
    code: number;
};

export type YandexMapInstance = {
    destroy: () => void;
    setCenter: (coords: Coordinates, zoom?: number, options?: Record<string, unknown>) => void;
    setBounds: (bounds: number[][], options?: Record<string, unknown>) => void;
    geoObjects: {
        add: (object: unknown) => void;
        removeAll: () => void;
    };
};

export type YandexMapsApi = {
    ready: (callback: () => void) => void;
    Map: new (
        element: HTMLElement,
        state: { center: Coordinates; zoom: number; controls?: string[] },
        options?: Record<string, unknown>,
    ) => YandexMapInstance;
    Placemark: new (
        coords: Coordinates,
        properties?: Record<string, unknown>,
        options?: Record<string, unknown>,
    ) => { events: { add: (eventName: string, callback: () => void) => void } };
};
