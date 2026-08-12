import assert from 'node:assert/strict';
import test from 'node:test';

import {
    getCdekAction,
    isCdekAction,
    readCdekRequestBody,
    toCdekOfficeParams,
} from './utils.ts';

test('CDEK request helpers validate actions and strip the internal action parameter', () => {
    const body = readCdekRequestBody({ action: 'offices', city_code: 44 });

    assert.equal(getCdekAction(body, null), 'offices');
    assert.equal(isCdekAction('calculate'), true);
    assert.equal(isCdekAction('unknown'), false);
    assert.equal(toCdekOfficeParams(Object.entries(body)).toString(), 'city_code=44');
    assert.deepEqual(readCdekRequestBody(null), {});
});
