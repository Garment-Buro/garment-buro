export const YANDEX_METRIKA_COUNTER_ID = 112566503;

const YANDEX_METRIKA_HOSTS = new Set([
    'garment-buro.ru',
    'www.garment-buro.ru',
]);

export const isYandexMetrikaHost = (hostname: string) =>
    YANDEX_METRIKA_HOSTS.has(hostname.toLowerCase());

