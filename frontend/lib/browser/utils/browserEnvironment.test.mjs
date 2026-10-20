import assert from 'node:assert/strict';
import test from 'node:test';

import { detectBrowserSurface } from './detectBrowserSurface.ts';
import { getPageChrome, isSiteChromeHidden } from './pageChrome.ts';
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
    assert.equal(getPageChrome('/').page, 'home');
    assert.equal(getPageChrome('/index').page, 'home');
    assert.equal(getPageChrome('/presentation').page, 'presentation');
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

test('direct order URLs retain the home background without a second site header', () => {
    assert.equal(getPageChrome('/order/123').page, 'home');
    assert.equal(getPageChrome('/order/123').pageColor, '#77745A');
    assert.equal(isSiteChromeHidden('/order/123'), true);
    assert.equal(isSiteChromeHidden('/order-policy'), false);
    for (const pathname of ['/order/success', '/order/error', '/order/123/extra']) {
        assert.equal(isSiteChromeHidden(pathname), false);
        assert.equal(getPageChrome(pathname).page, 'default');
    }
});

test('public profile screens use their own navigation without a floating site header over fields', () => {
    for (const pathname of ['/people/member-one', '/profile/public']) assert.equal(isSiteChromeHidden(pathname), true);
    assert.equal(isSiteChromeHidden('/people-policy'), false);
    assert.equal(isSiteChromeHidden('/profile/public-policy'), false);
});
