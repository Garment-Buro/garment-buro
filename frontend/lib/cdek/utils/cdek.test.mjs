import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';
import vm from 'node:vm';
import fs from 'node:fs';

const source = fs.readFileSync(new URL('./cdek.ts', import.meta.url), 'utf8');
const compiled = ts.transpile(source, {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
});
const runtimeModule = { exports: {} };
vm.runInNewContext(compiled, { module: runtimeModule, exports: runtimeModule.exports, Intl });

const { filterCdekOffices, getOfficeCoords, pickCdekTariff, sanitizeCdekCityCode } = runtimeModule.exports;
const offices = [
    { code: 'A', name: 'Тверская', location: { latitude: 55.76, longitude: 37.61 } },
    { code: 'B', name: 'Арбат', location: { latitude: 55.75, longitude: 37.59 } },
];

test('filterCdekOffices supports text search and distance ordering', () => {
    assert.deepEqual(filterCdekOffices(offices, 'арбат', null).map((office) => office.code), ['B']);
    assert.equal(filterCdekOffices(offices, '', [55.75, 37.59])[0].code, 'B');
});

test('CDEK helpers normalize API and form data', () => {
    assert.deepEqual(JSON.parse(JSON.stringify(getOfficeCoords(offices[0]))), [55.76, 37.61]);
    assert.equal(pickCdekTariff({ tariff_codes: [{ delivery_sum: 420 }] }).delivery_sum, 420);
    assert.equal(sanitizeCdekCityCode('44 test'), '44');
});
