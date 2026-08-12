import type { BrowserSurface } from '@/lib/browser/types';

type BrowserNavigator = Navigator & { standalone?: boolean };

export const isStandaloneDisplayMode = (targetWindow: Window, targetNavigator: BrowserNavigator) => (
    targetWindow.matchMedia('(display-mode: standalone)').matches || targetNavigator.standalone === true
);

export const detectBrowserSurface = (
    targetWindow: Window = window,
    targetNavigator: BrowserNavigator = navigator,
): BrowserSurface => {
    if (isStandaloneDisplayMode(targetWindow, targetNavigator)) return 'pwa';

    const userAgent = targetNavigator.userAgent;
    const isIOS = /iPad|iPhone|iPod/.test(userAgent)
        || (targetNavigator.platform === 'MacIntel' && targetNavigator.maxTouchPoints > 1);
    const isSafari = /Safari/.test(userAgent)
        && !/(CriOS|FxiOS|EdgiOS|OPiOS|Chrome|Chromium|Android)/.test(userAgent);

    if (!isIOS || !isSafari) return 'otherbrowser';

    const safariVersion = Number(userAgent.match(/Version\/(\d+)/)?.[1] || 0);
    return safariVersion >= 26 ? 'safari26' : 'safari18';
};
