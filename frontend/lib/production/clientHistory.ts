import type { AdminClientOrder, AdminClientTicket } from './adminTypes.ts';

export type ClientHistoryQuery = { key: string; cursor?: string | null };
export type ClientHistoryPage<Item> = { items: Item[]; next_cursor: string | null };
const invalid = () => new Error('Сервер вернул неверную историю клиента.');
const record = (value: unknown): Record<string, unknown> => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw invalid();
    return value as Record<string, unknown>;
};
const text = (value: unknown) => typeof value === 'string';
const nullableText = (value: unknown) => value === null || text(value);
const id = (value: unknown) => Number.isSafeInteger(value) && Number(value) > 0;
const timestamp = (value: unknown) => text(value) && Number.isFinite(Date.parse(value as string));

function readPage<Item>(value: unknown, read: (value: unknown) => Item & { id: number }): ClientHistoryPage<Item> {
    const page = record(value);
    if (!Array.isArray(page.items) || page.items.length > 100
        || !(page.next_cursor === null || (text(page.next_cursor) && String(page.next_cursor).length > 0 && String(page.next_cursor).length <= 2048))) throw invalid();
    const items = page.items.map(read);
    if (new Set(items.map(item => item.id)).size !== items.length) throw invalid();
    return { items, next_cursor: page.next_cursor as string | null };
}

export function readClientOrders(value: unknown): ClientHistoryPage<AdminClientOrder> {
    return readPage(value, value => {
        const item = record(value);
        if (!id(item.id) || !timestamp(item.created_at) || !text(item.total)
            || !/^\d+(?:\.\d{1,2})?$/.test(String(item.total)) || !Number.isFinite(Number(item.total))
            || !text(item.status) || !text(item.payment_status) || !nullableText(item.workflow_state)
            || !nullableText(item.delivery_city) || !nullableText(item.delivery_method) || !nullableText(item.payment_method)) throw invalid();
        return item as unknown as AdminClientOrder;
    });
}

export function readClientTickets(value: unknown): ClientHistoryPage<AdminClientTicket> {
    return readPage(value, value => {
        const item = record(value);
        if (!id(item.id) || !text(item.subject) || !timestamp(item.created_at) || !timestamp(item.updated_at)
            || !['new', 'in_progress', 'resolved', 'closed'].includes(String(item.status))
            || !['low', 'normal', 'high', 'critical'].includes(String(item.priority))
            || !(item.order_id === null || id(item.order_id))) throw invalid();
        return item as unknown as AdminClientTicket;
    });
}
