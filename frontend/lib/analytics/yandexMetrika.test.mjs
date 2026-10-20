import assert from 'node:assert/strict';
import test from 'node:test';

import {
    getPublicAnalyticsPage,
    isYandexMetrikaHost,
    YANDEX_METRIKA_COUNTER_ID,
} from './yandexMetrika.ts';

const origin = 'https://garment-buro.ru';
const secret = 'SYNTHETIC_PRIVATE_' + 'Q'.repeat(43);
test('Metrika only accepts production HTTPS origins and known public pages', () => {
    assert.equal(YANDEX_METRIKA_COUNTER_ID, 112566503);
    for (const host of ['garment-buro.ru', 'www.garment-buro.ru']) {
        assert.equal(isYandexMetrikaHost(host), true);
        assert.equal(getPublicAnalyticsPage(`https://${host}/catalog`).url, origin + '/catalog');
    }
    for (const url of [
        'http://garment-buro.ru/', 'https://garment-buro.ru:444/',
        'https://user:password@garment-buro.ru/', 'not a URL',
        ...['dev', 'partner', 'production', 'widget'].map(host => `https://${host}.garment-buro.ru/`),
        'https://garment-buro.ru.example.invalid/',
    ]) assert.equal(getPublicAnalyticsPage(url), null, url);
});

test('query, hash, profile/landing identities and unknown paths never enter analytics', () => {
    assert.deepEqual(getPublicAnalyticsPage(`${origin}/?email=${secret}#${secret}`), {
        url: origin + '/', title: 'Главная',
    });
    assert.deepEqual(getPublicAnalyticsPage(`${origin}/p/${secret}?project=${secret}`), {
        url: origin + '/p/community', title: 'Сообщество',
    });
    assert.deepEqual(getPublicAnalyticsPage(`${origin}/people/${secret}`), {
        url: origin + '/people/profile', title: 'Публичный профиль',
    });
    for (const path of [
        '/constructor', '/unfinished', '/profile', '/profile/public', '/lk', '/mycollection',
        '/checkout', '/order/success', '/order/error', '/order/' + secret,
        '/admin', '/partner', '/production', '/login', '/dev', '/unknown/' + secret,
        '/api/design-media/' + secret + '/content', '/storage/private/' + secret,
    ]) assert.equal(getPublicAnalyticsPage(origin + path), null, path);
});

