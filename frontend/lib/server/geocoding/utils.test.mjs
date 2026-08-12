import assert from 'node:assert/strict';
import test from 'node:test';

import {
    buildAddressSearchParams,
    normalizeAddressSuggestions,
} from './utils.ts';

test('address search keeps provider query generation outside the route', () => {
    assert.equal(
        buildAddressSearchParams('Тверская 10', 'Москва').get('q'),
        'Тверская 10, Москва',
    );
    assert.equal(
        buildAddressSearchParams('Москва, Тверская 10', 'Москва').get('q'),
        'Москва, Тверская 10',
    );
});

test('address suggestions discard malformed provider content', () => {
    assert.deepEqual(
        normalizeAddressSuggestions([
            { display_name: 'Москва, Тверская 10', lat: '55.1', lon: '37.2' },
            { name: 'Без координат' },
            null,
        ], 'Тверская 10'),
        [{
            value: 'Москва, Тверская 10',
            displayName: 'Москва, Тверская 10',
            coords: [55.1, 37.2],
        }],
    );
    assert.deepEqual(normalizeAddressSuggestions({ error: true }, 'Адрес'), []);
});
