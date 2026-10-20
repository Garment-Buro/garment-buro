import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const read = (...parts) => fs.readFileSync(path.join(root, ...parts), 'utf8');
const sharedLinkSource = read('components', 'shared', 'Link.tsx');

test('shared Link stays independent from settings and editor behavior', () => {
    assert.doesNotMatch(sharedLinkSource, /useSettingsStore|usePathname|window\.prompt|settings\.links/);
    assert.match(sharedLinkSource, /<NextLink/);
});
