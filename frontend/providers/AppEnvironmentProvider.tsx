'use client';

import {
    createContext,
    useContext,
    useLayoutEffect,
    useMemo,
    type ReactNode,
} from 'react';
import { usePathname } from 'next/navigation';

import { useBrowserSurface } from '@/hooks/browser/useBrowserSurface';
import type { BrowserSurface, PageChromeConfig } from '@/lib/browser/types';
import { getPageChrome } from '@/lib/browser/utils/pageChrome';

type AppEnvironmentValue = {
    surface: BrowserSurface;
    pageChrome: PageChromeConfig;
};

const AppEnvironmentContext = createContext<AppEnvironmentValue | null>(null);

type AppEnvironmentProviderProps = {
    children: ReactNode;
};

export function AppEnvironmentProvider({ children }: AppEnvironmentProviderProps) {
    const pathname = usePathname();
    const surface = useBrowserSurface();
    const pageChrome = getPageChrome(pathname);

    useLayoutEffect(() => {
        const topColor = pageChrome.topColor;
        const bottomOffset = surface === 'pwa'
            ? '0px'
            : surface === 'otherbrowser'
                ? (pageChrome.otherBottomOffset || '0px')
                : pageChrome.bottomOffset;

        const html = document.documentElement;
        const body = document.body;
        const metaThemeColor = document.querySelector('meta[name="theme-color"]') as HTMLMetaElement | null;
        const previousThemeMedia = metaThemeColor?.getAttribute('media');
        const usesNativeSafariColor = surface === 'safari26'
            && ['nikitamoiseev', 'light-running', 'presentation'].includes(pageChrome.page);
        let secondThemeRefreshId: number | undefined;

        const syncPageChrome = () => {
            const isConstructorOverlayActive = pageChrome.page === "constructor"
                && (html.dataset.constructorOverlayActive === "true"
                    || body.dataset.constructorOverlayActive === "true");
            const activeTopColor = isConstructorOverlayActive ? "#FFFFFF" : topColor;

            html.dataset.browserSurface = surface;
            html.dataset.appPage = pageChrome.page;
            body.dataset.browserSurface = surface;
            body.dataset.appPage = pageChrome.page;
            html.style.setProperty('--app-top-color', activeTopColor);
            html.style.setProperty('--app-page-color', pageChrome.pageColor);
            html.style.setProperty('--app-page-bottom-offset', bottomOffset);
            body.style.setProperty('--app-top-color', activeTopColor);
            body.style.setProperty('--app-page-color', pageChrome.pageColor);
            body.style.setProperty('--app-page-bottom-offset', bottomOffset);
            if (metaThemeColor) {
                metaThemeColor.content = activeTopColor;
                // Safari 26 samples the real page edge for its glass toolbar.
                // Do not pin a competing solid tint on immersive public pages.
                if (usesNativeSafariColor) metaThemeColor.setAttribute('media', 'not all');
                else if (previousThemeMedia == null) metaThemeColor.removeAttribute('media');
                else metaThemeColor.setAttribute('media', previousThemeMedia);
            }
        };

        syncPageChrome();
        const themeRefreshId = window.requestAnimationFrame(() => {
            syncPageChrome();
            secondThemeRefreshId = window.requestAnimationFrame(syncPageChrome);
        });
        const themeRefreshTimer = window.setTimeout(syncPageChrome, 120);
        const overlayObserver = new MutationObserver(syncPageChrome);
        const overlayObserverOptions: MutationObserverInit = {
            attributes: true,
            attributeFilter: ["data-constructor-overlay-active"],
        };
        overlayObserver.observe(html, overlayObserverOptions);
        overlayObserver.observe(body, overlayObserverOptions);

        return () => {
            window.cancelAnimationFrame(themeRefreshId);
            if (secondThemeRefreshId !== undefined) window.cancelAnimationFrame(secondThemeRefreshId);
            window.clearTimeout(themeRefreshTimer);
            overlayObserver.disconnect();
            if (metaThemeColor) {
                if (previousThemeMedia == null) metaThemeColor.removeAttribute('media');
                else metaThemeColor.setAttribute('media', previousThemeMedia);
            }
        };
    }, [pageChrome, surface]);

    const value = useMemo(() => ({ surface, pageChrome }), [pageChrome, surface]);

    return (
        <AppEnvironmentContext.Provider value={value}>
            <div className="appSafariTopBar" data-app-top-page={pageChrome.page} aria-hidden="true" />
            {children}
        </AppEnvironmentContext.Provider>
    );
}

export const useAppEnvironment = () => {
    const environment = useContext(AppEnvironmentContext);
    if (!environment) {
        throw new Error('useAppEnvironment must be used inside AppEnvironmentProvider');
    }
    return environment;
};
