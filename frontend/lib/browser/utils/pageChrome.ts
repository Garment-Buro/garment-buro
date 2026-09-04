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
    {
        page: "nikitamoiseev",
        topColor: "#E8F1F8",
        pageColor: "#E8F1F8",
        bottomOffset: "0px",
        otherBottomOffset: "0px",
    },
    {
        page: "partner",
        topColor: "#E7EEF1",
        pageColor: "#E7EEF1",
        bottomOffset: "0px",
        otherBottomOffset: "0px",
    },
];

const SITE_CHROME_HIDDEN_ROUTES = new Set([
    '/',
    '/checkout',
    '/constructor',
    '/unfinished',
    '/lk',
    '/mycollection',
    '/profile',
    '/light-running',
    '/nikitamoiseev',
]);

export const isSiteChromeHidden = (pathname: string | null) => (
    pathname !== null && (
        SITE_CHROME_HIDDEN_ROUTES.has(pathname)
        || pathname.startsWith('/partner')
        || pathname.startsWith('/p/')
    )
);

export const getPageChrome = (pathname: string | null): PageChromeConfig => {
    if (pathname === '/') return PAGE_CHROME[0];
    if (pathname?.startsWith('/constructor')) return PAGE_CHROME[1];
    if (pathname?.startsWith('/product')) return PAGE_CHROME[2];
    if (pathname?.startsWith('/unfinished')) return PAGE_CHROME[3];
    if (pathname === '/lk' || pathname === '/mycollection' || pathname === '/profile') return PAGE_CHROME[4];
    if (pathname === '/light-running') return PAGE_CHROME[5];
    if (pathname === '/nikitamoiseev') return PAGE_CHROME[6];
    if (pathname?.startsWith('/partner')) return PAGE_CHROME[7];
    return DEFAULT_PAGE_CHROME;
};
