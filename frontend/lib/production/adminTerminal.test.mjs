import assert from 'node:assert/strict';
import test from 'node:test';
import { isSplashHiddenRoute } from '../browser/utils/splash.ts';
import { isCookieConsentHiddenRoute } from '../browser/utils/cookieConsent.ts';

test('nested production terminals never show storefront splash or consent overlays', () => {
    for (const path of ['/production', '/production/admin', '/production/floor']) {
        assert.equal(isSplashHiddenRoute(path), true);
        assert.equal(isCookieConsentHiddenRoute(path), true);
    }
    assert.equal(isSplashHiddenRoute('/production-other'), false);
    assert.equal(isCookieConsentHiddenRoute('/production-other'), false);
});
