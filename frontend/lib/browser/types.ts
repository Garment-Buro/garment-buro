export type BrowserSurface = 'pwa' | 'safari26' | 'safari18' | 'otherbrowser';

export type AppPage = 'default' | 'catalog' | 'constructor' | 'product' | 'unfinished' | 'profile' | 'light-running';

export type PageChromeConfig = {
    page: AppPage;
    topColor: string;
    pageColor: string;
    bottomOffset: string;
    otherBottomOffset?: string;
};
