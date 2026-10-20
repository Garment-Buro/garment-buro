import assert from 'node:assert/strict';
import test from 'node:test';
import { customerOrderStatus } from './customerStatus.ts';

test('payment and workflow are separate facts for every customer stage', () => {
    for (const stage of ['awaiting_payment', 'moderation', 'production', 'shipped', 'completed', 'cancelled', 'attention']) {
        for (const payment of ['pending', 'paid', 'failed', 'unknown', null]) {
            const result = customerOrderStatus({ status: 'new', customer_stage: stage, customer_stage_label: `Server ${stage}`, payment_status: payment });
            assert.equal(result.label, `Server ${stage}`);
            assert.equal(result.paymentLabel, ({ pending: 'Оплата не подтверждена', paid: 'Оплата подтверждена', failed: 'Оплата не прошла' })[payment] ?? 'Статус оплаты неизвестен');
            if (stage === 'cancelled') assert.equal(result.tone, 'error');
            else if (stage === 'attention') assert.equal(result.tone, 'neutral');
            else if (payment === 'failed') assert.equal(result.tone, 'error');
            else if (payment === 'paid' && ['production', 'shipped', 'completed'].includes(stage)) assert.equal(result.tone, 'success');
            else assert.equal(result.tone, 'neutral');
        }
    }
});

test('unknown or missing states cannot imply success or expose internal codes', () => {
    assert.deepEqual(customerOrderStatus({ status: 'future_internal_state', payment_status: 'provider_pending' }), {
        label: 'Статус заказа уточняется', paymentLabel: 'Статус оплаты неизвестен', tone: 'neutral',
    });
    assert.equal(customerOrderStatus({ status: 'new', payment_status: 'paid' }).tone, 'neutral');
    assert.equal(customerOrderStatus({ status: 'processing', payment_status: 'paid', customer_stage: 'future_stage' }).tone, 'neutral');
    assert.equal(customerOrderStatus({ status: 'processing', payment_status: 'paid' }).tone, 'success');
    assert.equal(customerOrderStatus({ status: 'cancelled', payment_status: 'paid' }).tone, 'error');
});
