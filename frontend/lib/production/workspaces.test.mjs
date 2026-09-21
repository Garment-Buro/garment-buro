import assert from 'node:assert/strict';
import test from 'node:test';
import {
    bagCanMove,
    parseBagReference,
    queueItemMatchesPocket,
    queueItemMatchesStation,
    resolveEmployeeStation,
    stationGuides,
} from './workspaces.ts';

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
test('the cycle documents the shared workshop and preserves legacy stations', () => {
    assert.equal(Object.keys(stationGuides).length, 11);
    assert.ok(stationGuides.workshop);
    assert.ok(stationGuides.application);
    assert.match(stationGuides.dtf.result, /комплектовщик/);
});

test('public labels only accept local random tokens', () => {
    const origin = 'https://production.garment-buro.ru';
    const token = 'a'.repeat(43);
    assert.deepEqual(parseBagReference(`${origin}/production/label?token=${token}`, origin), {kind:'label',token});
    assert.equal(parseBagReference(`${origin}/production/label?token=1`, origin), null);
    assert.equal(parseBagReference(`https://evil.test/production/label?token=${token}`, origin), null);
});

test('terminal queue respects display states and station counters', () => {
    const item = {
        project_id: 1,
        order_id: 10,
        customer: 'Test',
        units_count: 2,
        state: 'in_production',
        display_state: 'done',
        version: 1,
        paid_at: null,
        blocked: false,
        flow_version: 2,
        stage_counts: { workshop: 2, waiting_dtf: 1 },
        dtf_pending: 1,
    };
    assert.equal(queueItemMatchesPocket(item, 'done'), true);
    assert.equal(queueItemMatchesPocket(item, 'holds'), true);
    assert.equal(queueItemMatchesStation(item, 'workshop'), true);
    assert.equal(queueItemMatchesStation(item, 'dtf'), true);
    assert.equal(queueItemMatchesStation(item, 'packing'), false);
    assert.equal(
        queueItemMatchesStation(
            { ...item, state: 'inbox', stage_counts: {}, dtf_pending: 0, dtf_approved: false },
            'dtf',
        ),
        true,
    );
    assert.equal(
        queueItemMatchesStation(
            { ...item, state: 'inbox', stage_counts: {}, dtf_pending: 0, dtf_approved: true },
            'dtf',
        ),
        false,
    );
});

test('the first assigned station is also used for API actions before manual switching', () => {
    assert.equal(resolveEmployeeStation(undefined, ['cut', 'packing']), 'cut');
    assert.equal(resolveEmployeeStation('packing', ['cut', 'packing']), 'packing');
    assert.equal(resolveEmployeeStation(undefined, []), undefined);
});
