import assert from 'node:assert/strict';
import test from 'node:test';
import {buildModelPayload, emptyModel, emptySize, toModelEditor, readModelUpload} from './modelEditor.ts';

test('model payload keeps exact dimensions, strips archived sizes and read-only fields', () => {
    const source = {...emptyModel(), id: 130, version: 7, sizes: [
        {...emptySize(5), id: 81, code: 'M', base_price: '80.00', base_width_cm: '64.25', base_length_cm: '72.35', extra_width_price_per_cm: '3.25', is_active: true, version: 4},
        {...emptySize(9), id: 82, code: 'ARCHIVED', is_active: false},
    ], size_chart_media_object_id: 44};
    const draft = toModelEditor(source);
    assert.equal(draft.size_chart_url, '/api/production/admin/assortment/media/public/44');
    assert.equal(draft.sizes.length, 1);
    assert.equal(draft.sizes[0].id, 81);
    const payload = buildModelPayload(draft);
    assert.equal(payload.expected_version, 7);
    assert.equal(payload.sizes[0].base_width_cm, '64.25');
    assert.equal(payload.sizes[0].base_length_cm, '72.35');
    assert.equal(payload.sizes[0].extra_width_price_per_cm, '3.25');
    assert.equal(payload.sizes[0].sort_order, 0);
    assert.equal('id' in payload.sizes[0], false);
    assert.equal('version' in payload.sizes[0], false);
    assert.equal('size_chart_url' in payload, false);
});

test('model write refuses invalid decimals, missing versions and excessive size grids', () => {
    for (const value of ['NaN', 'Infinity', '1e999', '1.234', '-1']) {
        const draft = emptyModel(); draft.sizes[0].base_width_cm = value;
        assert.throws(() => buildModelPayload(draft));
    }
    assert.throws(() => buildModelPayload({...emptyModel(), id: 1}));
    assert.throws(() => buildModelPayload({...emptyModel(), sizes: Array.from({length:101}, (_, i) => emptySize(i))}));
    assert.equal('expected_version' in buildModelPayload(emptyModel()), false);
});

test('model media requires a confirmed positive ID and builds the authenticated preview URL', () => {
    for (const value of [null, {}, {id:0}, {id:-1}, {id:1.1}, {id:'1'}, {id:Infinity}, {id:Number.MAX_SAFE_INTEGER+1}])
        assert.throws(() => readModelUpload(value));
    assert.deepEqual(readModelUpload({id:44, url:'javascript:ignored'}), {id:44, url:'/api/production/admin/assortment/media/public/44'});
});
