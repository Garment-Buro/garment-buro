import type { AdminOrder } from '@/lib/orders/types';
import {
    formatOrderDate,
    formatOrderPrice,
    getOrderStatusClassName,
    getOrderStatusLabel,
} from '@/lib/orders/utils/orderFormatting';

type AdminOrdersTableProps = {
    orders: AdminOrder[];
};

export function AdminOrdersTable({ orders }: AdminOrdersTableProps) {
    return (
        <div className="bg-white rounded-md shadow-sm border border-black/10 overflow-hidden text-black">
            <table className="w-full text-left border-collapse">
                <thead>
                    <tr className="bg-gray-50 border-b border-black/10">
                        <th className="p-4 font-semibold">ID</th>
                        <th className="p-4 font-semibold">Дата</th>
                        <th className="p-4 font-semibold">Клиент</th>
                        <th className="p-4 font-semibold">Сумма</th>
                        <th className="p-4 font-semibold">Статус</th>
                    </tr>
                </thead>
                <tbody>
                    {orders.length > 0 ? orders.map((order) => (
                        <tr key={order.id} className="border-b border-black/5 hover:bg-gray-50">
                            <td className="p-4">{order.id}</td>
                            <td className="p-4">{formatOrderDate(order.created_at)}</td>
                            <td className="p-4">
                                <div>{order.first_name} {order.last_name || ''}</div>
                                <div className="text-sm text-gray-500">{order.phone}</div>
                            </td>
                            <td className="p-4">{formatOrderPrice(order.total_price)}</td>
                            <td className="p-4">
                                <span className={`px-2 py-1 rounded text-sm ${getOrderStatusClassName(order.status)}`}>
                                    {getOrderStatusLabel(order.status)}
                                </span>
                            </td>
                        </tr>
                    )) : (
                        <tr>
                            <td colSpan={5} className="p-6 text-center text-gray-500">Нет заказов</td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
}
