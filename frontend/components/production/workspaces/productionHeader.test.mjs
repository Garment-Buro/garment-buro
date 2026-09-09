import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

test('mobile header reserves identity width and never wraps email character by character', () => {
    const css = readFileSync(new URL('./ProductionFlow.module.css', import.meta.url), 'utf8');
    const source = readFileSync(new URL('./ProductionWorkspace.tsx', import.meta.url), 'utf8');
    assert.match(css, /\.account strong\s*\{[^}]*text-overflow: ellipsis;[^}]*white-space: nowrap;/);
    assert.match(css, /@media \(max-width: 560px\)[\s\S]*grid-template-columns: 40px minmax\(0, 1fr\) auto/);
    assert.match(source, /className=\{styles\.adminLink\}/);
    assert.match(source, /title=\{employee\?\.name\}/);
});
