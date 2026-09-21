import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

test('mobile header reserves identity width and never wraps email character by character', () => {
    const css = readFileSync(new URL('./ProductionFlow.module.css', import.meta.url), 'utf8');
    const source = readFileSync(new URL('./ProductionWorkspace.tsx', import.meta.url), 'utf8');
    assert.match(css, /\.account strong\s*\{[^}]*text-overflow: ellipsis;[^}]*white-space: nowrap;/);
    assert.match(css, /@media \(max-width: 720px\)[\s\S]*\.topbarInner\s*\{[\s\S]*grid-template-columns: 40px minmax\(0, 1fr\) auto/);
    assert.match(source, /className=\{styles\.adminLink\}/);
    assert.match(source, /title=\{employee\?\.name\}/);
});

test('every employee station uses the desktop workspace and mobile master-detail state', () => {
    const css = readFileSync(new URL('./ProductionFlow.module.css', import.meta.url), 'utf8');
    const source = readFileSync(new URL('./ProductionWorkspace.tsx', import.meta.url), 'utf8');
    assert.match(css, /\.page\s*\{[^}]*max-width:\s*1600px;/s);
    assert.match(css, /\.layout\s*\{[^}]*grid-template-columns:\s*minmax\(300px, 360px\) minmax\(0, 1fr\);/s);
    assert.doesNotMatch(css, /\.page\s*\{[^}]*max-width:\s*430px;/s);
    assert.match(css, /\.layout\[data-selected='true'\] \.queue\s*\{[^}]*display:\s*none;/s);
    assert.match(source, /data-selected=\{Boolean\(terminal\.selected\)\}/);
    assert.match(source, /className=\{styles\.mobileDetailBack\}/);
});
