'use client';

import { useEffect, useRef } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';

import {
    isYandexMetrikaHost,
    YANDEX_METRIKA_COUNTER_ID,
} from '@/lib/analytics/yandexMetrika';

type YandexMetrikaFunction = ((...arguments_: unknown[]) => void) & {
    a?: unknown[][];
    l?: number;
};

declare global {
    interface Window {
        dataLayer?: unknown[];
        ym?: YandexMetrikaFunction;
        __garmentBuroMetrikaInitialized?: boolean;
    }
}

const TAG_URL = `https://mc.yandex.ru/metrika/tag.js?id=${YANDEX_METRIKA_COUNTER_ID}`;

const initialize = () => {
    if (window.__garmentBuroMetrikaInitialized) return;

    const queued: YandexMetrikaFunction = (...arguments_) => {
        queued.a = queued.a || [];
        queued.a.push(arguments_);
    };
    queued.l = Date.now();
    window.ym = window.ym || queued;
    window.dataLayer = window.dataLayer || [];

    if (![...document.scripts].some((script) => script.src === TAG_URL)) {
        const script = document.createElement('script');
        script.async = true;
        script.src = TAG_URL;
        document.head.appendChild(script);
    }

    window.ym(YANDEX_METRIKA_COUNTER_ID, 'init', {
        ssr: true,
        defer: true,
        webvisor: true,
        clickmap: true,
        ecommerce: 'dataLayer',
        referrer: document.referrer,
        url: window.location.href,
        accurateTrackBounce: true,
        trackLinks: true,
    });
    window.__garmentBuroMetrikaInitialized = true;
};

export function YandexMetrika() {
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const previousUrl = useRef<string | null>(null);
    const query = searchParams.toString();

    useEffect(() => {
        if (!isYandexMetrikaHost(window.location.hostname)) return;

        initialize();
        const url = window.location.href;
        if (previousUrl.current === url) return;

        window.ym?.(YANDEX_METRIKA_COUNTER_ID, 'hit', url, {
            title: document.title,
            referer: previousUrl.current || document.referrer,
        });
        previousUrl.current = url;
    }, [pathname, query]);

    return null;
}

