import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const read = (...parts) => fs.readFileSync(path.join(root, ...parts), 'utf8');
const page = read('app', 'checkout', 'page.tsx');
const screen = read('components', 'checkout', 'CheckoutScreen.tsx');
const hook = read('hooks', 'checkout', 'useCheckout.ts');
const api = read('lib', 'api', 'checkout.ts');
const utils = read('lib', 'checkout', 'utils', 'checkout.ts');

test('/checkout page only composes the feature screen and hydration boundary', () => {
    assert.match(page, /CheckoutScreen/);
    assert.match(page, /useClientReady/);
    assert.doesNotMatch(page, /fetch\(|useState|useEffect|useCartStore/);
    assert.match(screen, /CheckoutFormColumn/);
    assert.match(screen, /CheckoutOrderSummary/);
});

test('/checkout keeps state, API and pure transformations in their feature layers', () => {
    assert.match(hook, /useCheckout/);
    assert.match(hook, /createCheckoutOrder|calculateCdekDelivery/);
    assert.match(api, /requestJson/);
    assert.match(utils, /formatRussianPhone|getCheckoutErrors|createCheckoutOrderPayload/);
    assert.doesNotMatch(screen, /fetch\(/);
});
