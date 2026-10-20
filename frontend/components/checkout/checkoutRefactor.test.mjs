import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const read = (...parts) => fs.readFileSync(path.join(root, ...parts), 'utf8');
const page = read('app', 'checkout', 'page.tsx');
const screen = read('components', 'checkout', 'CheckoutScreen.tsx');

test('/checkout page only composes the feature screen and hydration boundary', () => {
    assert.match(page, /CheckoutScreen/);
    assert.match(page, /useClientReady/);
    assert.doesNotMatch(page, /fetch\(|useState|useEffect|useCartStore/);
    assert.match(screen, /CheckoutFormColumn/);
    assert.match(screen, /CheckoutOrderSummary/);
});
