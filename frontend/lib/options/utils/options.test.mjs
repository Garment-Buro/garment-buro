import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';
import vm from 'node:vm';
import fs from 'node:fs';

const source = fs.readFileSync(new URL('./options.ts', import.meta.url), 'utf8');
const compiled = ts.transpile(source, {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    esModuleInterop: true,
});
const runtimeModule = { exports: {} };
vm.runInNewContext(compiled, { module: runtimeModule, exports: runtimeModule.exports });

const { appendColorOption, appendSizeOption, normalizeVariantOptions } = runtimeModule.exports;

test('normalizeVariantOptions replaces missing collections with empty arrays', () => {
    assert.deepEqual(
        JSON.parse(JSON.stringify(normalizeVariantOptions({ colors: undefined, sizes: ['M'] }))),
        { colors: [], sizes: ['M'] },
    );
});

test('option append helpers preserve the original options', () => {
    const options = { colors: [], sizes: ['S'] };
    const withColor = appendColorOption(options, { label: 'Красный', hex: '#f00' });
    const withSize = appendSizeOption(options, 'M');

    assert.equal(options.colors.length, 0);
    assert.deepEqual(JSON.parse(JSON.stringify(withColor.colors)), [{ label: 'Красный', hex: '#f00' }]);
    assert.deepEqual(JSON.parse(JSON.stringify(withSize.sizes)), ['S', 'M']);
});
