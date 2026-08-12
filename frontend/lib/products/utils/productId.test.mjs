import assert from 'node:assert/strict';
import test from 'node:test';

import { parseProductId } from './productId.ts';

test('product route accepts only positive integer identifiers', () => {
    assert.equal(parseProductId('12'), 12);
    assert.equal(parseProductId('0'), null);
    assert.equal(parseProductId('-1'), null);
    assert.equal(parseProductId('1.5'), null);
    assert.equal(parseProductId('product'), null);
});
