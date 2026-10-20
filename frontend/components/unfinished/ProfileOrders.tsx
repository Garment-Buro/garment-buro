'use client';

import { CustomerMediaImage } from '@/components/shared/CustomerMediaImage';
import { useAuthOrders } from '@/hooks/auth/useAuthOrders';
import type { UnfinishedSurfaceViewModel } from '@/hooks/unfinished/useUnfinishedSurface';
import { parseAuthOrderItems, getAuthOrderFitSummary } from '@/lib/auth/utils/auth';
import { customerOrderStatus } from '@/lib/orders/customerStatus';
import styles from './UnfinishedSurface.module.css';

const price = (value: string | number) => `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(value))} ₽`;

export function ProfileOrders({ surface }: { surface: UnfinishedSurfaceViewModel }) {
    const history = useAuthOrders(surface.expandedOrderId);
    if (history.loading) return <p role="status" className={styles.profileEmptyState}>Загружаем заказы…</p>;
    if (history.error && history.orders.length === 0) return <div className={styles.profileSettingsCard} role="alert">
        Не удалось загрузить заказы.
        <button className={styles.profilePrimaryButton} type="button" onClick={() => void history.retry()}>Повторить</button>
    </div>;
    const expanded = history.selected;
    if (expanded) return (
        <div className={styles.profileOrdersCard}>
            <div className={styles.orderExpandedHeader}>
                <span><strong>Заказ № {expanded.id}</strong><span>{price(expanded.total_price)}</span>
                    <span>{customerOrderStatus(history.order ?? expanded).label}</span>
                    <span>{customerOrderStatus(history.order ?? expanded).paymentLabel}</span>
                </span>
                <button className={`${styles.orderArrow} ${styles.orderArrowOpen}`} type="button" aria-label="Свернуть заказ" onClick={surface.handleCollapseOrder} />
            </div>
            {history.detailLoading && <p role="status" className={styles.profileEmptyState}>Загружаем состав заказа…</p>}
            {Boolean(history.detailError) && <div className={styles.profileInfoBlock} role="alert">Не удалось открыть заказ.
                <button type="button" className={styles.profilePrimaryButton} onClick={() => void history.retryDetail()}>Повторить открытие</button>
            </div>}
            {history.order && (
            <div className={styles.orderReceipt}>
                <span className={styles.profileSectionLabel}>СОСТАВ ЗАКАЗА</span>
                {parseAuthOrderItems(history.order.cart_items).map((item, index) => (
                    <div className={`${styles.orderProductRow} ${!item.image ? styles.orderProductRowWithoutImage : ''}`} key={index}>
                        {item.image && <CustomerMediaImage src={item.image} alt={item.title} width={42} height={42} unoptimized />}
                        <span><strong>{item.title}</strong>
                            {item.color && <span>Цвет: {item.color}</span>}
                            {item.size && <span>Размер: {item.size}</span>}
                            {getAuthOrderFitSummary(item) && <span>{getAuthOrderFitSummary(item)}</span>}
                        </span>
                    </div>
                ))}
                <div className={styles.orderTotals}><span><span>Итого</span><strong>{price(expanded.total_price)}</strong></span></div>
            </div>)}
            {(expanded.cdek_status || expanded.cdek_number) && <section className={styles.profileInfoBlock}>
                <span className={styles.profileSectionLabel}>ДОСТАВКА</span>
                {expanded.cdek_number && <span>СДЭК: {expanded.cdek_number}</span>}
                {expanded.cdek_status && <span>{expanded.cdek_status}</span>}
            </section>}
        </div>
    );
    return <div className={`${styles.profileOrdersCard} ${styles.profileOrdersListCard}`}>
        <div className={styles.orderSummaries}>
            {history.orders.length === 0 && <p className={styles.profileEmptyState}>Заказов пока нет.</p>}
            {history.orders.map(order => <button className={styles.orderSummary} type="button" key={order.id}
                aria-expanded={false} onClick={() => surface.handleToggleOrder(String(order.id))}>
                <span className={styles.orderSummaryText}><strong>Заказ № {order.id}</strong>
                    <span>{new Date(order.created_at).toLocaleDateString('ru-RU')} • {price(order.total_price)}</span>
                    <span>{customerOrderStatus(order).label}</span>
                    <span>{customerOrderStatus(order).paymentLabel}</span>
                </span><span className={styles.orderArrow} aria-hidden="true" />
            </button>)}
            {Boolean(history.error) && <p role="alert" className={styles.profileEmptyState}>Не удалось загрузить следующую страницу заказов.</p>}
            {history.hasMore && <button className={styles.profilePrimaryButton} type="button" disabled={history.loadingMore} onClick={() => void history.loadMore()}>
                {history.loadingMore ? 'Загружаем…' : history.error ? 'Повторить загрузку' : 'Показать ещё заказы'}
            </button>}
        </div>
    </div>;
}
