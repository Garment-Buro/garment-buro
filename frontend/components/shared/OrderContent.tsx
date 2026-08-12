"use client";

import React from 'react';
import { Text } from '@/components/shared/Text';
import { OrderStatusMark } from '@/components/orders/OrderStatusMark';
import { useOrderDetails } from '@/hooks/orders/useOrderDetails';
import { buildOrderDetailRows, getOrderFitSummary, parseOrderItems } from '@/lib/orders/utils/orderDetails';

// ─── Main component ─────────────────────────────────────────────────────────
interface OrderContentProps {
    orderId?: string | string[];
}

export const OrderContent: React.FC<OrderContentProps> = ({ orderId: propOrderId }) => {
    const { order, isLoading } = useOrderDetails(propOrderId);

    // ── Loading ──
    if (isLoading) {
        return (
            <div className="p-10 text-center">
                <Text size={15} className="text-[#999]">Загрузка данных заказа...</Text>
            </div>
        );
    }

    // ── Error / Not found ──
    if (!order) {
        return (
            <div className="p-8 pb-10 text-center">
                <OrderStatusMark variant="error" />
                <Text size={20} weight="semibold" className="text-black mb-2 mt-2">Заказ не найден</Text>
                <Text size={14} className="text-[#666]">Проверьте номер заказа или вернитесь на главную</Text>
            </div>
        );
    }

    // ── Success ──
    const isCancelled = order.status === 'cancelled';
    const items = parseOrderItems(order.cart_items);
    const rows = buildOrderDetailRows(order);

    return (
        <div className="p-8 pb-10">
            {/* Icon */}
            <div className="mb-2">
                <OrderStatusMark variant={isCancelled ? 'error' : 'success'} />
            </div>

            <Text size={22} weight="semibold" className="text-black mb-6">Заказ #{order.id}</Text>

            {/* Detail rows */}
            <div className="flex flex-col mb-8">
                {rows.map(({ label, value }) => (
                    <div key={label} className="flex justify-between py-[10px] border-b border-black/8">
                        <Text size={15} className="text-[#666]">{label}:</Text>
                        <Text size={15} weight="medium" className="text-black">{value}</Text>
                    </div>
                ))}
            </div>

            {/* Items */}
            <Text size={18} className="text-black mb-4">Состав заказа</Text>
            <div className="flex flex-col gap-3">
                {items.map((item, idx) => (
                    <div key={idx} className="flex justify-between items-center p-4 bg-[#F7F7F7] rounded-[12px] gap-3">
                        <div className="flex flex-col gap-1 min-w-0">
                            <Text size={14} weight="medium" className="text-black">{item.title}</Text>
                            {(item.color || item.size) && (
                                <Text size={12} className="text-[#888]">
                                    {[item.color && `Цвет: ${item.color}`, item.size && `Размер: ${item.size}`].filter(Boolean).join(' | ')}
                                </Text>
                            )}
                            {getOrderFitSummary(item) && (
                                <Text size={12} className="text-[#888]">{getOrderFitSummary(item)}</Text>
                            )}
                        </div>
                        <Text size={14} className="text-black shrink-0">
                            {item.quantity} шт. x {item.price?.toLocaleString('ru-RU')} ₽
                        </Text>
                    </div>
                ))}
            </div>

            {/* Track button — max 280px */}
            <div className="mt-8 flex justify-center">
                <button className="w-full max-w-[280px] h-[50px] rounded-[12px] bg-[linear-gradient(180deg,rgba(243,243,243,0.6)_0%,rgba(220,220,220,0.6)_100%)] shadow-[inset_0_1px_3px_0_rgba(0,0,0,0.2)] text-black transition-opacity hover:opacity-80 cursor-pointer">
                    <Text size={15} className="tracking-wide text-black">отследить заказ</Text>
                </button>
            </div>
        </div>
    );
};
