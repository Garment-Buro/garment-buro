import assert from 'node:assert/strict';
import test from 'node:test';

import {
    getCollapsedPanelOpenState,
    getGridItems,
    getPanelStepState,
    getScrollProgress,
    isPersistedDraft,
} from './unfinished.ts';

const draft = { id: 'draft', kind: 'draft', number: '001', name: 'Draft', imageSrc: '/draft.webp', productId: 1, savedAt: 1 };
const collection = { id: 'collection', kind: 'collection', number: '001', name: 'Collection', imageSrc: '/collection.webp', productId: 2, savedAt: 1 };

test('unfinished grid selection follows the active surface', () => {
    assert.deepEqual(getGridItems('unfinished', [draft], [collection]), [draft]);
    assert.deepEqual(getGridItems('my-collection', [draft], [collection]), [collection]);
    assert.deepEqual(getGridItems('profile', [draft], [collection]), []);
    assert.equal(isPersistedDraft(draft), true);
    assert.equal(isPersistedDraft({ ...draft, savedAt: 0 }), false);
});

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
