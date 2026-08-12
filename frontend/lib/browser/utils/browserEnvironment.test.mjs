import assert from 'node:assert/strict';
import test from 'node:test';

import { detectBrowserSurface } from './detectBrowserSurface.ts';
import { getPageChrome } from './pageChrome.ts';
import { isCookieConsentHiddenRoute } from './cookieConsent.ts';

const createWindow = (standalone = false) => ({
    matchMedia: () => ({ matches: standalone }),
});

const createNavigator = (userAgent, standalone = false) => ({
    userAgent,
    standalone,
    platform: 'iPhone',
    maxTouchPoints: 5,
});

test('browser surface keeps PWA, Safari 26, legacy Safari and other browsers distinct', () => {
    assert.equal(detectBrowserSurface(createWindow(true), createNavigator('Safari Version/26')), 'pwa');
    assert.equal(detectBrowserSurface(createWindow(), createNavigator('iPhone Safari Version/26')), 'safari26');
    assert.equal(detectBrowserSurface(createWindow(), createNavigator('iPhone Safari Version/18')), 'safari18');
    assert.equal(detectBrowserSurface(createWindow(), createNavigator('iPhone CriOS Version/26')), 'otherbrowser');
});

test('page chrome maps routes to reusable page variants', () => {
    assert.equal(getPageChrome('/').page, 'catalog');
    assert.equal(getPageChrome('/product/1').page, 'product');
    assert.equal(getPageChrome('/constructor').pageColor, '#FFFFFF');
    assert.equal(getPageChrome('/lk').page, 'profile');
    assert.equal(getPageChrome('/contacts').page, 'default');
});

test('cookie consent keeps route visibility rules outside the component', () => {
    assert.equal(isCookieConsentHiddenRoute('/checkout'), true);
    assert.equal(isCookieConsentHiddenRoute('/unfinished'), true);
    assert.equal(isCookieConsentHiddenRoute('/lk'), true);
    assert.equal(isCookieConsentHiddenRoute('/product/1'), false);
});
