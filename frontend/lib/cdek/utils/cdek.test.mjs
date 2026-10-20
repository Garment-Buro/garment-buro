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

const { getOfficeTitle, getOfficeAddress, getOfficeCoords } = runtimeModule.exports;
const offices = [
    { code: 'A', name: 'Тверская', location: { latitude: 55.76, longitude: 37.61 } },
    { code: 'B', name: 'Арбат', location: { latitude: 55.75, longitude: 37.59 } },
];

test('checkout displays the directory title and preferred full address with fallbacks', () => {
    assert.equal(getOfficeTitle(offices[0]), 'Тверская');
    assert.equal(getOfficeTitle({ code: 'C' }), 'C');
    assert.equal(getOfficeAddress({ location: { address_full: 'Город, улица, 1', address: 'улица, 1' } }), 'Город, улица, 1');
    assert.equal(getOfficeAddress({ location: { address: 'улица, 1' } }), 'улица, 1');
    assert.equal(getOfficeAddress({ code: 'C' }), 'Адрес не указан');
});

test('checkout map coordinates stay numeric and missing coordinates stay absent', () => {
    assert.deepEqual(JSON.parse(JSON.stringify(getOfficeCoords(offices[0]))), [55.76, 37.61]);
    assert.equal(getOfficeCoords({ code: 'C' }), null);
    assert.equal(getOfficeCoords({ location: { latitude: 55.76 } }), null);
    assert.equal(getOfficeCoords({ location: { latitude: '55.76', longitude: 37.61 } }), null);
    assert.deepEqual(JSON.parse(JSON.stringify(getOfficeCoords({ location: { latitude: 0, longitude: 0 } }))), [0, 0]);
});
