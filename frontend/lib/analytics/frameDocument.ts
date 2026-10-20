import {
    PUBLIC_ANALYTICS_ORIGIN,
    PUBLIC_ANALYTICS_PAGES,
    YANDEX_METRIKA_COUNTER_ID,
    YANDEX_METRIKA_PRIVACY_OPTIONS,
} from './yandexMetrika';

// The SDK runs in an opaque origin: no parent DOM, cookies, storage, navigation
// or forms. Served from its own fixed URL; srcdoc would inherit the parent base URL.
export const PUBLIC_ANALYTICS_FRAME_HTML = `<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' https://mc.yandex.ru; connect-src https://mc.yandex.ru https://mc.yandex.com; img-src https://mc.yandex.ru https://mc.yandex.com; frame-src 'none'; base-uri 'none'; form-action 'none'">
<title>Garment Buro analytics</title></head><body><script>
(() => {
    const pages = ${JSON.stringify(PUBLIC_ANALYTICS_PAGES)};
    const counter = ${YANDEX_METRIKA_COUNTER_ID};
    const options = ${JSON.stringify(YANDEX_METRIKA_PRIVACY_OPTIONS)};
    const origin = ${JSON.stringify(PUBLIC_ANALYTICS_ORIGIN)};
    let initialized = false, previous = null;
    window.ym = function() { (window.ym.a = window.ym.a || []).push(arguments); };
    window.ym.l = Date.now();
    window.addEventListener('message', event => {
        if (event.source !== parent || ![origin, 'https://www.garment-buro.ru'].includes(event.origin)
            || event.data?.type !== 'gb-public-page') return;
        const page = pages.find(page => page.url === event.data.url);
        if (!page || page.url === previous) return;
        if (!initialized) {
            window.ym(counter, 'init', { ...options, url: page.url, referrer: origin + '/' });
            initialized = true;
        }
        window.ym(counter, 'hit', page.url, { title: page.title, referer: previous || origin + '/' });
        previous = page.url;
    });
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://mc.yandex.ru/metrika/tag.js';
    script.referrerPolicy = 'no-referrer';
    script.onload = () => parent.postMessage({ type: 'gb-analytics-ready' }, '*');
    script.onerror = () => parent.postMessage({ type: 'gb-analytics-unavailable' }, '*');
    document.head.appendChild(script);
})();
</script></body></html>`;
