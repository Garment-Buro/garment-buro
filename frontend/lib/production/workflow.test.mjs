import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { canAct, currentStage, orderBlocked, safeImage } from './workflow.ts';

test('explicit demo orders do not need payment but still respect production stops', () => {
    const demo = { is_demo: true, payment_status: 'pending', order_status: 'processing', project_status: 'queued' };
    assert.equal(orderBlocked(demo), false);
    assert.equal(orderBlocked({ ...demo, is_demo: false }), true);
    assert.equal(orderBlocked({ ...demo, project_status: 'on_hold' }), true);
});

test('floor actions require an explicitly assigned role including technologists', () => {
    assert.equal(canAct(['cut'], 'shipping'), false);
    assert.equal(canAct(['cut'], 'cut'), true);
    assert.equal(canAct(['tech'], 'shipping'), false);
    assert.equal(canAct(['tech', 'packing'], 'packing'), true);
    assert.equal(
        currentStage({
            specification: { route: ['cut', 'qc', 'packing'] },
            stage_index: 1,
        }),
        'qc',
    );
    assert.equal(currentStage({ specification: null, stage_index: 0 }), null);
});
test('unpaid, stopped or shipped orders are not editable', () => {
    const project = {
        payment_status: 'paid',
        order_status: 'processing',
        project_status: 'in_progress',
    };
    assert.equal(orderBlocked(project), false);
    for (const patch of [
        { payment_status: 'refunded' },
        { order_status: 'shipped' },
        { project_status: 'on_hold' },
    ])
        assert.equal(orderBlocked({ ...project, ...patch }), true);
});
test('preview never accepts executable or transient image URLs', () => {
    for (const source of [
        'javascript:alert(1)',
        '//outside.test/img',
        'blob:temporary',
        'data:text/html,test',
    ])
        assert.equal(safeImage(source), null);
    assert.equal(safeImage('/orders/photo.png'), '/orders/photo.png');
    assert.equal(
        safeImage('https://test.example/image.png'),
        'https://test.example/image.png',
    );
});
test('production is isolated from consumer chrome and offline document caching', () => {
    const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
    assert.match(read('../../proxy.ts'), /production\.garment-buro\.ru/);
    assert.match(
        read('../../public/sw.js'),
        /url\.pathname\.startsWith\('\/production'\)\) return/,
    );
    assert.match(
        read('../browser/utils/pageChrome.ts'),
        /pathname\.startsWith\('\/production'\)/,
    );
    assert.match(read('../browser/utils/splash.ts'), /'\/production'/);
});
