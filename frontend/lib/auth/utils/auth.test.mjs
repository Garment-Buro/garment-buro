import assert from 'node:assert/strict';
import test from 'node:test';

import {
    createAuthProfileData,
    getAuthOrderFitSummary,
    hasUsableAuthToken,
    normalizeOtpCode,
    normalizeOtpDigit,
    parseAuthOrderItems,
} from './auth.ts';

test('parseAuthOrderItems returns order items and tolerates invalid payloads', () => {
    assert.deepEqual(parseAuthOrderItems('[{"title":"Платье"}]'), [{ title: 'Платье' }]);
    assert.deepEqual(parseAuthOrderItems('{"title":"Платье"}'), []);
    assert.deepEqual(parseAuthOrderItems('broken'), []);
});

test('getAuthOrderFitSummary formats reusable fit information', () => {
    assert.equal(getAuthOrderFitSummary({ title: 'Платье' }), null);
    assert.equal(getAuthOrderFitSummary({
        title: 'Платье',
        customization: { fit: { lengthCm: 120, widthCm: 52, sleeveMode: 'height' } },
    }), 'Посадка: длина 120, ширина 52, рукава под рост');
});

test('auth helpers normalize persisted values and editable profile data', () => {
    assert.equal(hasUsableAuthToken('token'), true);
    assert.equal(hasUsableAuthToken('null'), false);
    assert.equal(normalizeOtpDigit('a12'), '2');
    assert.equal(normalizeOtpCode('1a2345'), '1234');
    assert.deepEqual(createAuthProfileData(null), {
        first_name: '', gender: '', birth_date: '', phone: '', email: '',
    });
});

