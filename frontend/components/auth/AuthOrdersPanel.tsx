import { CustomerMediaImage } from '@/components/shared/CustomerMediaImage';

import { useAuthOrders } from '@/hooks/auth/useAuthOrders';
import { getAuthOrderFitSummary, parseAuthOrderItems } from '@/lib/auth/utils/auth';

import { Text } from '@/components/shared/Text';
import { customerOrderStatus } from '@/lib/orders/customerStatus';

export const AuthOrdersPanel = () => {
    const history = useAuthOrders();
    const { orders, expandedOrderId, toggleOrder, loading, error, retry } = history;

    if (loading) return <p role="status">Загружаем заказы…</p>;
    if (error && orders.length === 0) return <div role="alert">Не удалось загрузить заказы. <button onClick={() => void retry()}>Повторить</button></div>;

    if (orders.length === 0) {
        return (
            <div className="text-center py-20">
                <Text className="text-[#A0A0A0]">У вас пока нет заказов</Text>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-4">
            {orders.map(order => {
                const items = history.order?.id === order.id ? parseAuthOrderItems(history.order.cart_items) : [];
                const status = customerOrderStatus(history.order?.id === order.id ? history.order : order);
                return (
                    <div key={order.id} className="bg-white rounded-[15px] overflow-hidden shadow-sm">
                        <button
                            type="button" aria-expanded={expandedOrderId === order.id}
                            onClick={() => toggleOrder(order.id)}
                            className="w-full p-4 flex items-center justify-between cursor-pointer hover:bg-[#FAFAFA] text-left"
                        >
                            <span className="flex flex-col">
                                <Text size={16} weight="bold" className="text-black">Заказ № {order.id.toString().padStart(3, '0')}</Text>
                                <Text size={12} className="text-[#A0A0A0]">{order.total_price} ₽ • {new Date(order.created_at).toLocaleDateString('ru-RU')}</Text>
                                <Text size={12}>{status.label}</Text>
                                <Text size={12}>{status.paymentLabel}</Text>
                                {(order.cdek_number || order.cdek_status) && (
                                    <Text size={12} className="text-[#A0A0A0] mt-1 wrap-break-word">
                                        {order.cdek_number ? `СДЭК: ${order.cdek_number}` : ''}
                                        {order.cdek_number && order.cdek_status ? ' • ' : ''}
                                        {order.cdek_status ? `Статус: ${order.cdek_status}` : ''}
                                    </Text>
                                )}
                            </span>
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className={`transition-transform ${expandedOrderId === order.id ? 'rotate-180' : ''}`}>
                                <path d="M6 9L12 15L18 9" stroke="#A0A0A0" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                        </button>
                        {expandedOrderId === order.id && (
                            <div className="p-4 border-t border-[#F0F0F0] bg-[#FAFAFA]">
                                {history.detailLoading && <p role="status">Загружаем состав заказа…</p>}
                                {Boolean(history.detailError) && <div role="alert">Не удалось открыть заказ.
                                    <button type="button" onClick={() => void history.retryDetail()}>Повторить открытие</button>
                                </div>}
                                {items.map((item, index) => {
                                    const fitSummary = getAuthOrderFitSummary(item);
                                    return (
                                        <div key={index} className="flex gap-4 mb-3 last:mb-0">
                                            <div className="w-12 h-16 bg-[#F0F0F0] rounded relative overflow-hidden">
                                                {item.image && <CustomerMediaImage src={item.image} alt={item.title} fill className="object-cover" />}
                                            </div>
                                            <div className="flex flex-col">
                                                <Text size={12} weight="bold" className="text-black">{item.title}</Text>
                                                {(item.size || item.color) && <Text size={12} className="text-[#A0A0A0]">{[item.size, item.color].filter(Boolean).join(' / ')}</Text>}
                                                {fitSummary && <Text size={12} className="text-[#A0A0A0]">{fitSummary}</Text>}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                );
            })}
            {Boolean(error) && <p role="alert">Не удалось загрузить следующую страницу заказов.</p>}
            {history.hasMore && <button type="button" disabled={history.loadingMore} onClick={() => void history.loadMore()}>
                {history.loadingMore ? 'Загружаем…' : error ? 'Повторить загрузку' : 'Показать ещё заказы'}
            </button>}
        </div>
    );
};

