import assert from 'node:assert/strict';
import test from 'node:test';

import { createDecryptedTextFrame, randomizeText } from './decryptedText.ts';

const frame = (revealDirection, iteration, text = 'ABCD') => createDecryptedTextFrame({
    text,
    iteration,
    totalIterations: 4,
    revealDirection,
    sequential: true,
    getRandomCharacter: () => '?',
});

test('decrypted text frames preserve directional reveal order', () => {
    assert.equal(frame('start', 2), 'AB??');
    assert.equal(frame('end', 2), '??CD');
    assert.equal(frame('center', 1, 'ABCDE'), '??C??');
});

test('non-sequential frames reveal only on the final iteration', () => {
    const options = {
        text: 'A B',
        totalIterations: 3,
        revealDirection: 'start',
        sequential: false,
        getRandomCharacter: () => '?',
    };
    assert.equal(createDecryptedTextFrame({ ...options, iteration: 2 }), '? ?');
    assert.equal(createDecryptedTextFrame({ ...options, iteration: 3 }), 'A B');
    assert.equal(randomizeText('A B', () => '!'), '! !');
});
