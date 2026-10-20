export const YANDEX_MAPS_API_KEY = process.env.NEXT_PUBLIC_YANDEX_MAPS_API_KEY || '';

export const YANDEX_MAPS_SCRIPT_ID = 'yandex-maps-script';
export const YANDEX_MAPS_SCRIPT_URL = `https://api-maps.yandex.ru/2.1/?lang=ru_RU&apikey=${YANDEX_MAPS_API_KEY}`;
