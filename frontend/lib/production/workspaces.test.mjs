import assert from 'node:assert/strict';
import test from 'node:test';
import { bagCanMove, parseBagReference, stationGuides } from './workspaces.ts';

test('scanner resolves numbers and local bag QR without falling back to another order', () => {
    const origin = 'https://production.garment-buro.ru';
    assert.deepEqual(parseBagReference('#1002', origin), {
        kind: 'order',
        id: 1002,
    });
    assert.deepEqual(
        parseBagReference(
            `${origin}/production?project=31&unit=9#unit-9`,
            origin,
        ),
        { kind: 'project', id: 31, unit: 9 },
    );
    for (const input of [
        'abc',
        '0',
        '-3',
        '9007199254740992',
        `${origin}/other?project=1`,
        'https://evil.test/production?project=1',
        'javascript:alert(1)',
    ]) {
        assert.equal(parseBagReference(input, origin), null, input);
    }
});
const unit = {
    specification: {
        components: [{ key: 'fabric' }],
        route: ['cut', 'application', 'sewing'],
    },
    checks: { fabric: false },
    issue: null,
    blockers: [],
    dtf_inserted: false,
};
test('whole bag transfer requires every component and every waiting DTF, not one item', () => {
    assert.equal(bagCanMove({ state: 'kitting', units: [unit] }), false);
    assert.equal(
        bagCanMove({
            state: 'kitting',
            units: [{ ...unit, checks: { fabric: true } }],
        }),
        true,
    );
    assert.equal(bagCanMove({ state: 'waiting_dtf', units: [unit] }), false);
    assert.equal(
        bagCanMove({
            state: 'waiting_dtf',
            units: [{ ...unit, dtf_inserted: true }],
        }),
        true,
    );
    assert.equal(bagCanMove({ state: 'kitting', units: [] }), false);
    assert.equal(
        bagCanMove({
            state: 'waiting_dtf',
            units: [{ ...unit, dtf_inserted: true, issue: 'defect' }],
        }),
        false,
    );
});
test('the complete cycle covers all ten workstations including separate application', () => {
    assert.equal(Object.keys(stationGuides).length, 10);
    assert.ok(stationGuides.application);
    assert.match(stationGuides.dtf.result, /комплектовщик/);
});
