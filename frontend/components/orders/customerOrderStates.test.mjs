import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const require = createRequire(import.meta.url);
const root = process.cwd();
let currentOrder;
let currentHistory;
function load(file) {
    const compiled = ts.transpile(fs.readFileSync(file, 'utf8'), {
        module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
        jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true,
    });
    const runtimeModule = { exports: {} };
    const localRequire = name => {
        if (name === '@/hooks/orders/useOrderDetails') return { useOrderDetails: () => ({ order: currentOrder, retry() {} }) };
        if (name === '@/hooks/auth/useAuthOrders') return { useAuthOrders: () => currentHistory };
        if (name.endsWith('.module.css')) return {};
        if (name === '@/components/shared/Text') return { Text: ({ children, className }) => React.createElement('span', { className }, children) };
        if (name.startsWith('@/')) {
            const base = path.join(root, name.slice(2));
            return load(fs.existsSync(base + '.tsx') ? base + '.tsx' : base + '.ts');
        }
        if (name.startsWith('.')) {
            const base = path.resolve(path.dirname(file), name);
            return load(path.extname(base) ? base : base + '.ts');
        }
        return require(name);
    };
    vm.runInNewContext(compiled, { module: runtimeModule, exports: runtimeModule.exports, require: localRequire, Intl, Date });
    return runtimeModule.exports;
}
const { OrderContent } = load(path.join(root, 'components/shared/OrderContent.tsx'));
const baseOrder = { id: 42, status: 'new', payment_status: 'pending', total_price: 100,
    created_at: '2026-10-17T10:00:00Z', delivery_method: 'cdek_pickup', cart_items: '[]' };

test('an unpaid order has a neutral mark and explicit unconfirmed payment', () => {
    currentOrder = baseOrder;
    const html = renderToStaticMarkup(React.createElement(OrderContent));
    assert.match(html, /aria-label="Статус требует ожидания или проверки"/);
    assert.match(html, /Оплата не подтверждена/);
    assert.doesNotMatch(html, /aria-label="Заказ оплачен"/);
    assert.doesNotMatch(html, /отследить заказ/);
    assert.match(html, /Обновить статус/);
});

test('workflow attention overrides a paid order success mark without hiding payment facts', () => {
    currentOrder = { ...baseOrder, payment_status: 'paid', customer_stage: 'attention',
        customer_stage_label: 'Требуется проверка менеджера' };
    const html = renderToStaticMarkup(React.createElement(OrderContent));
    assert.match(html, /aria-label="Статус требует ожидания или проверки"/);
    assert.match(html, /Требуется проверка менеджера/);
    assert.match(html, /Оплата подтверждена/);
});

test('cancellation remains visible separately from a confirmed historical payment', () => {
    currentOrder = { ...baseOrder, status: 'cancelled', payment_status: 'paid',
        customer_stage: 'cancelled', customer_stage_label: 'Отменён', cdek_number: '123456789' };
    const html = renderToStaticMarkup(React.createElement(OrderContent));
    assert.match(html, /aria-label="Заказ отменён или оплата не прошла"/);
    assert.match(html, /Отменён/);
    assert.match(html, /Оплата подтверждена/);
    assert.match(html, /123456789/);
});

test('both history presentations show pending payment even without a workflow', () => {
    currentHistory = { orders: [baseOrder], expandedOrderId: null, loading: false };
    const { AuthOrdersPanel } = load(path.join(root, 'components/auth/AuthOrdersPanel.tsx'));
    const { ProfileOrders } = load(path.join(root, 'components/unfinished/ProfileOrders.tsx'));
    for (const element of [React.createElement(AuthOrdersPanel), React.createElement(ProfileOrders, { surface: {} })]) {
        const html = renderToStaticMarkup(element);
        assert.match(html, /Заказ создан/);
        assert.match(html, /Оплата не подтверждена/);
    }
});

test('both expanded histories prefer the fresh document state to an older summary', () => {
    const order = { ...baseOrder, payment_status: 'paid', customer_stage: 'attention', customer_stage_label: 'Требуется проверка менеджера' };
    currentHistory = { orders: [baseOrder], selected: baseOrder, expandedOrderId: 42, order, loading: false };
    const { AuthOrdersPanel } = load(path.join(root, 'components/auth/AuthOrdersPanel.tsx'));
    const { ProfileOrders } = load(path.join(root, 'components/unfinished/ProfileOrders.tsx'));
    for (const element of [React.createElement(AuthOrdersPanel), React.createElement(ProfileOrders, { surface: {} })]) {
        const html = renderToStaticMarkup(element);
        assert.match(html, /Требуется проверка менеджера/);
        assert.match(html, /Оплата подтверждена/);
        assert.doesNotMatch(html, /Оплата не подтверждена/);
    }
});
