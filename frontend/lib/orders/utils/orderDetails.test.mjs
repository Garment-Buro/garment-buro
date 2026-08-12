import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';
import vm from 'node:vm';
import fs from 'node:fs';

const source = fs.readFileSync(new URL('./orderDetails.ts', import.meta.url), 'utf8');
const compiled = ts.transpile(source, {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
});
const runtimeModule = { exports: {} };
vm.runInNewContext(compiled, { module: runtimeModule, exports: runtimeModule.exports });

const { buildOrderDetailRows, getOrderFitSummary, parseOrderItems } = runtimeModule.exports;

test('parseOrderItems handles invalid data without breaking the order page', () => {
    assert.deepEqual(JSON.parse(JSON.stringify(parseOrderItems('{broken'))), []);
    assert.deepEqual(JSON.parse(JSON.stringify(parseOrderItems('[{"title":"Худи"}]'))), [{ title: 'Худи' }]);
});

test('getOrderFitSummary describes constructor fit', () => {
    assert.equal(getOrderFitSummary({
        customization: { fit: { lengthCm: 70, widthCm: 60, sleeveMode: 'height' } },
    }), 'Посадка: длина 70, ширина 60, рукава под рост');
});

test('buildOrderDetailRows maps detail-specific labels', () => {
    const rows = buildOrderDetailRows({
        status: 'cancelled',
        total_price: 5980,
        created_at: '2026-07-16T00:00:00.000Z',
        delivery_method: 'cdek_pickup',
    });
    assert.equal(rows[0].value, 'Отменён');
    assert.equal(rows[3].value, 'СДЭК ПВЗ');
});
