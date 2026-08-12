import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const read = (...parts) => fs.readFileSync(path.join(root, ...parts), 'utf8');
const sharedLinkSource = read('components', 'shared', 'Link.tsx');
const footerLinkSource = read('components', 'layout', 'FooterLink.tsx');
const footerSource = read('components', 'layout', 'Footer.tsx');

test('shared Link stays independent from settings and editor behavior', () => {
    assert.doesNotMatch(sharedLinkSource, /useSettingsStore|usePathname|window\.prompt|settings\.links/);
    assert.match(sharedLinkSource, /<NextLink/);
});

test('footer settings are owned by a dedicated feature component', () => {
    assert.match(footerLinkSource, /useSettingsStore/);
    assert.match(footerLinkSource, /configuredLink\?\.label \|\| label/);
    assert.match(footerLinkSource, /configuredLink\?\.url \|\| href/);
    assert.match(footerLinkSource, /pathname === '\/admin\/editor'/);
    assert.match(footerLinkSource, /updateSettings\(\{/);
    assert.match(footerSource, /PRIMARY_LINKS\.map|links\.map/);
    assert.match(footerSource, /<FooterLinkList links=\{PRIMARY_LINKS\}/);
    assert.match(footerSource, /<FooterLinkList links=\{SECONDARY_LINKS\}/);
});
