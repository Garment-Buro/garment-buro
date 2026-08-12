import Image from 'next/image';

import { useAuthOrders } from '@/hooks/auth/useAuthOrders';
import { getAuthOrderFitSummary, parseAuthOrderItems } from '@/lib/auth/utils/auth';

import { Text } from '@/components/shared/Text';

export const AuthOrdersPanel = ({ token }: { token: string | null }) => {
    const { orders, expandedOrderId, toggleOrder } = useAuthOrders(token);

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
                const items = parseAuthOrderItems(order.cart_items);
                return (
                    <div key={order.id} className="bg-white rounded-[15px] overflow-hidden shadow-sm">
                        <button
                            onClick={() => toggleOrder(order.id)}
                            className="w-full p-4 flex items-center justify-between cursor-pointer hover:bg-[#FAFAFA] text-left"
                        >
                            <span className="flex flex-col">
                                <Text size={16} weight="bold" className="text-black">Заказ № {order.id.toString().padStart(3, '0')}</Text>
                                <Text size={12} className="text-[#A0A0A0]">{order.total_price} ₽ • {new Date(order.created_at).toLocaleDateString()}</Text>
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
                                {items.map((item, index) => {
                                    const fitSummary = getAuthOrderFitSummary(item);
                                    return (
                                        <div key={index} className="flex gap-4 mb-3 last:mb-0">
                                            <div className="w-12 h-16 bg-[#F0F0F0] rounded relative overflow-hidden">
                                                {item.image && <Image src={item.image} alt={item.title} fill className="object-cover" />}
                                            </div>
                                            <div className="flex flex-col">
                                                <Text size={12} weight="bold" className="text-black">{item.title}</Text>
                                                <Text size={12} className="text-[#A0A0A0]">{item.size} / {item.color}</Text>
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
        </div>
    );
};

