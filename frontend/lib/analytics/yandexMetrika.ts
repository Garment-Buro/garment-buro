export const YANDEX_METRIKA_COUNTER_ID = 112566503;

const YANDEX_METRIKA_HOSTS = new Set([
    'garment-buro.ru',
    'www.garment-buro.ru',
]);

export const isYandexMetrikaHost = (hostname: string) =>
    YANDEX_METRIKA_HOSTS.has(hostname.toLowerCase());

export const PUBLIC_ANALYTICS_ORIGIN = 'https://garment-buro.ru';
const PUBLIC_PAGES = new Map([
    ['/', 'Главная'],
    ['/index', 'Главная'],
    ['/catalog', 'Каталог'],
    ['/presentation', 'Презентация'],
    ['/light-running', 'Light Running'],
    ['/nikitamoiseev', 'Никита Моисеев'],
    ['/about', 'О нас'],
    ['/contacts', 'Контакты'],
    ['/delivery', 'Доставка'],
    ['/payment', 'Оплата'],
    ['/policy', 'Политика конфиденциальности'],
    ['/offer', 'Оферта'],
    ['/consent', 'Согласие'],
    ['/consent-cookies', 'Cookie'],
]);

export type PublicAnalyticsPage = { url: string; title: string };

export const PUBLIC_ANALYTICS_PAGES: PublicAnalyticsPage[] = [
    ...[...PUBLIC_PAGES].filter(([path]) => path !== '/index')
        .map(([path, title]) => ({ url: PUBLIC_ANALYTICS_ORIGIN + path, title })),
    { url: PUBLIC_ANALYTICS_ORIGIN + '/p/community', title: 'Сообщество' },
    { url: PUBLIC_ANALYTICS_ORIGIN + '/people/profile', title: 'Публичный профиль' },
];

/** Never forward a query, fragment, arbitrary path/slug or document title. */
export function getPublicAnalyticsPage(href: string): PublicAnalyticsPage | null {
    try {
        const url = new URL(href);
        if (url.protocol !== 'https:' || url.port || url.username || url.password
            || !isYandexMetrikaHost(url.hostname)) return null;
        const title = PUBLIC_PAGES.get(url.pathname);
        if (title) return { url: PUBLIC_ANALYTICS_ORIGIN + (url.pathname === '/index' ? '/' : url.pathname), title };
        // Aggregate public landing/profile views; names and identifiers stay local.
        if (/^\/p\/[^/]+$/.test(url.pathname)) {
            return { url: PUBLIC_ANALYTICS_ORIGIN + '/p/community', title: 'Сообщество' };
        }
        if (/^\/people\/[^/]+$/.test(url.pathname)) {
            return { url: PUBLIC_ANALYTICS_ORIGIN + '/people/profile', title: 'Публичный профиль' };
        }
    } catch { /* Unknown/malformed locations are excluded. */ }
    return null;
}

export const YANDEX_METRIKA_PRIVACY_OPTIONS = {
    ssr: true,
    defer: true,
    webvisor: false,
    clickmap: false,
    ecommerce: false,
    trackLinks: false,
    trackHash: false,
    accurateTrackBounce: false,
    sendTitle: false,
    disableYtm: true,
} as const;

