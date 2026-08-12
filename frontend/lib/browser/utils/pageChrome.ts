import type { PageChromeConfig } from '@/lib/browser/types';

export const DEFAULT_PAGE_CHROME: PageChromeConfig = {
    page: "default",
    topColor: "#F2F2F2",
    pageColor: "#F2F2F2",
    bottomOffset: "0px",
    otherBottomOffset: "0px",
};

export const PAGE_CHROME: PageChromeConfig[] = [
    {
        page: "catalog",
        topColor: "#F2F2F2",
        pageColor: "#F2F2F2",
        bottomOffset: "0px",
        otherBottomOffset: "0px",
    },
    {
        page: "constructor",
        topColor: "#FFFFFF",
        pageColor: "#FFFFFF",
        bottomOffset: "0px",
        otherBottomOffset: "0px",
    },
    {
        page: "product",
        topColor: "#F2F2F2",
        pageColor: "#F2F2F2",
        bottomOffset: "0px",
        otherBottomOffset: "0px",
    },
    {
        page: "unfinished",
        topColor: "#FFFFFF",
        pageColor: "#FFFFFF",
        bottomOffset: "0px",
        otherBottomOffset: "0px",
    },
    {
        page: "profile",
        topColor: "#FFFFFF",
        pageColor: "#FFFFFF",
        bottomOffset: "0px",
        otherBottomOffset: "0px",
    },
    {
        page: "light-running",
        topColor: "#141414",
        pageColor: "#141414",
        bottomOffset: "0px",
        otherBottomOffset: "0px",
    },
];

const SITE_CHROME_HIDDEN_ROUTES = new Set([
    '/checkout',
    '/constructor',
    '/unfinished',
    '/lk',
    '/light-running',
]);

export const isSiteChromeHidden = (pathname: string | null) => (
    pathname !== null && SITE_CHROME_HIDDEN_ROUTES.has(pathname)
);

export const getPageChrome = (pathname: string | null): PageChromeConfig => {
    if (pathname === '/') return PAGE_CHROME[0];
    if (pathname?.startsWith('/constructor')) return PAGE_CHROME[1];
    if (pathname?.startsWith('/product')) return PAGE_CHROME[2];
    if (pathname?.startsWith('/unfinished')) return PAGE_CHROME[3];
    if (pathname === '/lk') return PAGE_CHROME[4];
    if (pathname === '/light-running') return PAGE_CHROME[5];
    return DEFAULT_PAGE_CHROME;
};
