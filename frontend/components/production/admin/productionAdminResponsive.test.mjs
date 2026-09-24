import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const terminal = readFileSync(
    new URL('./ProductionAdminTerminal.tsx', import.meta.url),
    'utf8',
);
const table = readFileSync(
    new URL('./AdminRecordsTable.tsx', import.meta.url),
    'utf8',
);
const orderDetails = readFileSync(
    new URL('./AdminOrderDetails.tsx', import.meta.url),
    'utf8',
);
const orderItem = readFileSync(
    new URL('./AdminOrderItem.tsx', import.meta.url),
    'utf8',
);
const clientDetails = readFileSync(
    new URL('./AdminClientDetails.tsx', import.meta.url),
    'utf8',
);
const createTicket = readFileSync(
    new URL('../../support/CreateTicket.tsx', import.meta.url),
    'utf8',
);
const payoutReview = readFileSync(
    new URL('./AdminPayoutReview.tsx', import.meta.url),
    'utf8',
);
const statistics = readFileSync(
    new URL('./AdminStatistics.tsx', import.meta.url),
    'utf8',
);
const records = readFileSync(
    new URL('./AdminRecords.tsx', import.meta.url),
    'utf8',
);
const css = readFileSync(
    new URL('./ProductionAdmin.module.css', import.meta.url),
    'utf8',
);

test('mobile admin keeps navigation compact and returns to changed content', () => {
    assert.match(css, /\.nav\s*\{[^}]*position:\s*sticky/s);
    assert.match(css, /\.nav\s*\{[^}]*overflow-x:\s*auto/s);
    assert.match(terminal, /matchMedia\('\(max-width: 720px\)'\)/);
    assert.match(terminal, /scrollIntoView\(\{/);
    assert.match(terminal, /PiFactory/);
    assert.match(css, /\.actions \.headerAction\s*\{[^}]*border-radius:\s*50%/s);
    assert.match(css, /\.actionLabel\s*\{[^}]*clip-path:\s*inset\(50%\)/s);
});

test('mobile record lists use grouped cards instead of squeezed tables', () => {
    assert.match(table, /data-primary="true"/);
    assert.match(table, /data-wide="true"/);
    assert.match(table, /data-tail="true"/);
    assert.match(table, /data-action="true"/);
    assert.match(
        css,
        /\.screen tbody tr,[\s\S]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/,
    );
    assert.match(css, /td\[data-primary='true'\]/);
    assert.match(css, /td\[data-action='true'\] button/);
    assert.match(table, /data-section=\{section\}/);
    assert.match(css, /grid-template-areas:\s*'order total'/s);
    assert.match(css, /grid-template-areas:\s*'payout amount'/s);
});

test('mobile filters, statistics and dialogs use dense touch layouts', () => {
    assert.match(
        css,
        /\.toolbar\s*\{[^}]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/s,
    );
    assert.match(
        css,
        /\.metrics\s*\{[^}]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/s,
    );
    assert.match(css, /\.breakdowns\s*\{[^}]*grid-template-columns:\s*1fr/s);
    assert.match(css, /\.modalBackdrop\s*\{[^}]*align-items:\s*flex-end/s);
    assert.match(css, /\.editorActions\s*\{[^}]*position:\s*sticky/s);
    assert.match(orderDetails, /className=\{styles\.orderDialog\}/);
    assert.match(payoutReview, /className=\{styles\.payoutDialog\}/);
    assert.match(orderDetails, /aria-modal="true"/);
    assert.match(payoutReview, /aria-modal="true"/);
    assert.match(
        css,
        /\.orderDialog,[\s\S]*height:\s*calc\(100dvh - max\(16px,/,
    );
});

test('overview cards navigate, show weekly changes and use icon refresh actions', () => {
    assert.match(statistics, /onNavigate\(metric\.section\)/);
    assert.match(statistics, /data\.week_change\.orders_count/);
    assert.match(statistics, /data\.week_change\.paid_orders_total/);
    assert.doesNotMatch(statistics, /data\.week_change\.employees_count/);
    assert.match(statistics, /за 7 дней/);
    assert.match(statistics, /PiArrowClockwise/);
    assert.match(records, /PiArrowClockwise/);
    assert.doesNotMatch(statistics, />\s*Обновить\s*</);
    assert.doesNotMatch(records, />\s*Обновить\s*</);
    assert.doesNotMatch(statistics, /Суммы включают доставку/);
    assert.match(css, /\.metricCard\s*\{[^}]*grid-column:\s*span 3/s);
    assert.match(
        css,
        /\.metricCard\[data-width='wide'\]\s*\{[^}]*grid-column:\s*span 4/s,
    );
});

test('orders and payouts expose sorting, client navigation and readable details', () => {
    assert.match(records, /const sortingOptions/);
    assert.match(records, /params\.set\('sort', sort\)/);
    assert.match(records, /params\.set\('direction', direction\)/);
    assert.match(table, /onClient\(row\)/);
    assert.match(terminal, /selectSection\('clients'\)/);
    assert.match(orderDetails, /<AdminOrderItem/);
    assert.doesNotMatch(orderDetails, /JSON\.stringify/);
    assert.match(orderItem, /Настройки конструктора/);
    assert.match(orderItem, /Комментарий клиента/);
    assert.match(clientDetails, /История заказов/);
    assert.match(clientDetails, /История обращений/);
    assert.match(clientDetails, /Данные клиента/);
    assert.match(clientDetails, /clients\/detail\?key=/);
    assert.match(clientDetails, /onTicket\(ticket\.id\)/);
    assert.match(clientDetails, /<CreateTicket/);
    assert.match(clientDetails, /customerUserId=\{client\.user_id \?\? undefined\}/);
    assert.match(clientDetails, /role="tablist"/);
    assert.match(clientDetails, /role="tabpanel"/);
    assert.match(clientDetails, /orderOptions=\{data\.orders\.map/);
    assert.match(clientDetails, /label: `Заказ №\$\{order\.id\}/);
    assert.match(createTicket, /orderOptions\.map/);
    assert.match(createTicket, /<select/);
    assert.match(createTicket, /Без привязки к заказу/);
    assert.doesNotMatch(records, /CreateTicket/);
    assert.doesNotMatch(orderDetails, /CreateTicket/);
    assert.match(css, /\.clientProfileGrid/);
    assert.match(css, /\.clientTabs/);
    assert.match(css, /\.clientTabContent/);
    assert.match(
        css,
        /@media \(max-width: 720px\)[\s\S]*\.clientProfileGrid\s*\{[^}]*grid-template-columns:\s*1fr/s,
    );
    assert.doesNotMatch(records, /Покупатели с заказами/);
    assert.match(payoutReview, /canReview/);
    assert.match(payoutReview, /PiX/);
});
