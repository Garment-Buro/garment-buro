import assert from 'node:assert/strict';
import test from 'node:test';

import {
    getCollapsedPanelOpenState,
    getPanelStepState,
    getScrollProgress,
} from './unfinished.ts';

test('bottom panel state helpers preserve swipe behavior', () => {
    assert.equal(getCollapsedPanelOpenState(true, 'settings'), 'expanded');
    assert.equal(getCollapsedPanelOpenState(true, 'orders'), 'normal');
    assert.equal(getPanelStepState('expanded', 50), 'normal');
    assert.equal(getPanelStepState('normal', 50), 'collapsed');
    assert.equal(getPanelStepState('normal', -50), 'expanded');
});

test('scroll progress stays normalized', () => {
    assert.equal(getScrollProgress(50, 200, 100), 0.5);
    assert.equal(getScrollProgress(500, 200, 100), 1);
    assert.equal(getScrollProgress(10, 100, 100), 0);
});
