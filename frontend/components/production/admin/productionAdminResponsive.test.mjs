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
const payoutReview = readFileSync(
    new URL('./AdminPayoutReview.tsx', import.meta.url),
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
    assert.match(css, /\.actions > :only-child\s*\{[^}]*grid-column:\s*1 \/ -1/s);
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
    assert.match(css, /\.modalBackdrop\s*\{[^}]*align-items:\s*flex-end/s);
    assert.match(css, /\.editorActions\s*\{[^}]*position:\s*sticky/s);
    assert.match(orderDetails, /className=\{styles\.orderDialog\}/);
    assert.match(payoutReview, /className=\{styles\.payoutDialog\}/);
    assert.match(orderDetails, /aria-modal="true"/);
    assert.match(payoutReview, /aria-modal="true"/);
});
