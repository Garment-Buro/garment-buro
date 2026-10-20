'use client';

import { PiChatCircle, PiCheckCircle, PiPackage } from 'react-icons/pi';
import type { useProductionClientOrders, useProductionClientTickets } from '@/hooks/production/useProductionClientHistory';
import { date, money, priorityLabels, statusLabels } from '@/lib/production/adminTypes';
import styles from './ProductionAdmin.module.css';

type OrderPage = ReturnType<typeof useProductionClientOrders>;
type TicketPage = ReturnType<typeof useProductionClientTickets>;

export function ClientHistoryControls({ page, total, label = 'Ещё записи' }: {
    page: Pick<OrderPage, 'loading' | 'loadingMore' | 'error' | 'hasMore' | 'cursorExpired' | 'loadMore' | 'retry'> & { items: readonly { id: number }[] };
    total: number;
    label?: string;
}) {
    return <div className={styles.pagination}>
        {page.loading ? <p role="status">Загружаем историю…</p> : <span role="status">Показано {page.items.length} из {total}</span>}
        {page.error && <p role="alert" className={styles.error}>{page.error}</p>}
        {page.error && <button type="button" disabled={page.loading || page.loadingMore} onClick={() => {
            if (page.items.length && !page.cursorExpired) void page.loadMore();
            else void page.retry();
        }}>{page.cursorExpired ? 'Обновить историю' : 'Повторить загрузку'}</button>}
        {page.hasMore && !page.error && <button type="button" disabled={page.loadingMore} onClick={() => void page.loadMore()}>
            {page.loadingMore ? 'Загружаем…' : label}
        </button>}
    </div>;
}

export function ClientOrders({ page, total, onOrder }: { page: OrderPage; total: number; onOrder: (id: number) => void }) {
    return <section className={styles.clientSection} role="tabpanel" id="client-panel-orders" aria-labelledby="client-tab-orders">
        <div className={styles.orderSectionHeading}><PiPackage aria-hidden /><h3>История заказов</h3></div>
        {page.items.length > 0 && <div className={styles.clientHistoryList}>{page.items.map(order => <button type="button" key={order.id} onClick={() => onOrder(order.id)}>
            <span className={styles.clientHistoryIcon}><PiPackage aria-hidden /></span>
            <span><strong>Заказ №{order.id}</strong>
                <small>{date(order.created_at)} · {statusLabels[order.workflow_state || order.status] || order.status}</small>
                <small>{[order.delivery_city, order.delivery_method].filter(Boolean).join(' · ') || 'Доставка не указана'}</small>
            </span>
            <span className={styles.clientHistoryValue}><strong>{money(order.total)}</strong>
                <small>{statusLabels[order.payment_status] || order.payment_status}</small>
            </span>
        </button>)}</div>}
        {!page.loading && !page.error && !page.items.length && <p className={styles.clientEmptyHistory}><PiPackage aria-hidden />Заказов пока нет</p>}
        <ClientHistoryControls page={page} total={total} label="Ещё заказы" />
    </section>;
}

export function ClientTickets({ page, total, onTicket }: { page: TicketPage; total: number; onTicket: (id: number) => void }) {
    return <section className={styles.clientSection} role="tabpanel" id="client-panel-tickets" aria-labelledby="client-tab-tickets">
        <div className={styles.orderSectionHeading}><PiChatCircle aria-hidden /><h3>История обращений</h3></div>
        {page.items.length > 0 && <div className={styles.clientHistoryList}>{page.items.map(ticket => <button type="button" key={ticket.id} onClick={() => onTicket(ticket.id)}>
            <span className={styles.clientHistoryIcon}><PiChatCircle aria-hidden /></span>
            <span><strong>{ticket.subject}</strong><small>Обращение №{ticket.id} · {date(ticket.created_at)}</small>
                <small>{ticket.order_id ? `Заказ №${ticket.order_id}` : 'Без заказа'}</small></span>
            <span className={styles.clientHistoryValue}><strong>{statusLabels[ticket.status]}</strong><small>{priorityLabels[ticket.priority]}</small></span>
        </button>)}</div>}
        {!page.loading && !page.error && !page.items.length && <p className={styles.clientEmptyHistory}><PiCheckCircle aria-hidden />Обращений пока нет</p>}
        <ClientHistoryControls page={page} total={total} label="Ещё обращения" />
    </section>;
}
