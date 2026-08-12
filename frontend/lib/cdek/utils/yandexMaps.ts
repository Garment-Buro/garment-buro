import type { YandexMapsApi } from '@/lib/cdek/types';
import { loadScriptOnce } from '@/lib/browser/utils/scriptLoader';
import {
    YANDEX_MAPS_SCRIPT_ID,
    YANDEX_MAPS_SCRIPT_URL,
} from '@/lib/browser/config/vendorScripts';

const getYandexMapsApi = () => (window as unknown as { ymaps?: YandexMapsApi }).ymaps;

export const loadYandexMaps = async () => {
    if (!getYandexMapsApi()) {
        await loadScriptOnce(YANDEX_MAPS_SCRIPT_ID, YANDEX_MAPS_SCRIPT_URL);
    }

    const api = getYandexMapsApi();
    if (!api) throw new Error('Yandex Maps API did not initialize');

    return new Promise<YandexMapsApi>((resolve) => {
        api.ready(() => resolve(api));
    });
};
