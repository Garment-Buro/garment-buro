import assert from 'node:assert/strict';
import test from 'node:test';

import {
    normalizeCdekOffices,
    normalizeCdekTariffs,
} from './normalize.ts';

test('CDEK offices expose only the application contract', () => {
    assert.deepEqual(
        normalizeCdekOffices([
            {
                code: 'MSK1',
                name: 'ПВЗ',
                unexpected: '<script>',
                phones: [{ number: '+70000000000', secret: true }, null],
                location: {
                    city: 'Москва',
                    latitude: 55.7,
                    longitude: 37.6,
                    internal: 'hidden',
                },
            },
            { name: 'Без кода' },
        ]),
        [{
            code: 'MSK1',
            name: 'ПВЗ',
            type: undefined,
            owner_code: undefined,
            work_time: undefined,
            nearest_station: undefined,
            note: undefined,
            phones: [{ number: '+70000000000' }],
            location: {
                city: 'Москва',
                address: undefined,
                address_full: undefined,
                latitude: 55.7,
                longitude: 37.6,
            },
        }],
    );
});

test('CDEK tariffs discard malformed provider values', () => {
    assert.deepEqual(
        normalizeCdekTariffs({
            tariff_codes: [
                { delivery_sum: 420, period_min: 2, tariff_name: 'Склад-дверь', raw: true },
                { delivery_sum: 'invalid' },
            ],
        }),
        {
            tariff_codes: [{
                delivery_sum: 420,
                period_min: 2,
                period_max: undefined,
                tariff_name: 'Склад-дверь',
            }],
        },
    );
    assert.deepEqual(normalizeCdekTariffs(null), { tariff_codes: [] });
});
