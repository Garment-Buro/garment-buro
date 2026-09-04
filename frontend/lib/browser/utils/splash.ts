export const SPLASH_SESSION_KEY = 'p2o_splash_session';
export const SPLASH_APP_RUN_KEY = '__p2oSplashHandledThisAppRun';
export const PWA_REFRESH_SPLASH_SKIP_KEY = 'p2o_skip_splash_once';

export const SPLASH_HIDDEN_ROUTES = new Set([
    '/checkout',
    '/constructor',
    '/unfinished',
    '/lk',
    '/offer',
    '/nikitamoiseev',
    '/partner',
]);

export const isSplashHiddenRoute = (pathname: string) => SPLASH_HIDDEN_ROUTES.has(pathname);
