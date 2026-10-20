import {
    getPublicAnalyticsPage,
} from './yandexMetrika';

/** One optional frame per root layout; only allowlisted public URLs cross it. */
export function createPublicAnalyticsFrame(browser: Window, document: Document) {
    let frame: HTMLIFrameElement | null = null;
    let ready = false;
    let disposed = false;
    let previous: string | null = null;

    const remove = () => {
        frame?.remove();
        frame = null;
        ready = false;
        previous = null;
    };
    const update = () => {
        if (disposed) return;
        const page = getPublicAnalyticsPage(browser.location.href);
        if (!page) { remove(); return; }
        if (!frame) {
            frame = document.createElement('iframe');
            frame.setAttribute('sandbox', 'allow-scripts');
            frame.setAttribute('referrerpolicy', 'no-referrer');
            frame.setAttribute('aria-hidden', 'true');
            frame.title = 'Статистика просмотров';
            frame.hidden = true;
            frame.src = '/analytics/frame';
            document.body.appendChild(frame);
        }
        if (ready && previous !== page.url) {
            // Opaque sandbox has no target origin. The target Window is fixed;
            // the message contains only a constant URL, never input or IDs.
            frame.contentWindow?.postMessage({ type: 'gb-public-page', url: page.url }, '*');
            previous = page.url;
        }
    };
    const onMessage = (event: MessageEvent) => {
        if (disposed || !frame || event.source !== frame.contentWindow || event.origin !== 'null') return;
        if (event.data?.type === 'gb-analytics-unavailable') { remove(); return; }
        if (event.data?.type !== 'gb-analytics-ready') return;
        ready = true;
        update(); // Recheck the real location after a delayed SDK load.
    };
    browser.addEventListener('message', onMessage);
    return {
        update,
        dispose() {
            disposed = true;
            remove();
            browser.removeEventListener('message', onMessage);
        },
    };
}
