import assert from 'node:assert/strict';
import test from 'node:test';

import {
    getCrmProjectStatusClassName,
    getCrmProjectStatusLabel,
} from './projectFormatting.ts';

test('CRM project statuses have complete Russian labels', () => {
    assert.deepEqual(
        ['queued', 'in_progress', 'on_hold', 'completed', 'cancelled']
            .map(getCrmProjectStatusLabel),
        ['В очереди', 'В работе', 'Приостановлен', 'Завершён', 'Отменён'],
    );
});

test('terminal and active CRM states remain visually distinct', () => {
    assert.equal(getCrmProjectStatusClassName('in_progress'), 'bg-blue-100 text-blue-800');
    assert.equal(getCrmProjectStatusClassName('completed'), 'bg-green-100 text-green-800');
    assert.equal(getCrmProjectStatusClassName('cancelled'), 'bg-red-100 text-red-800');
});
