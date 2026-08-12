const COOKIE_CONSENT_HIDDEN_ROUTES = new Set(['/checkout', '/constructor', '/unfinished', '/lk']);

export const isCookieConsentHiddenRoute = (pathname: string) => COOKIE_CONSENT_HIDDEN_ROUTES.has(pathname);
