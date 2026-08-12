'use client';

import { AdminOrdersTable } from '@/components/admin/AdminOrdersTable';
import { AdminPageShell } from '@/components/admin/AdminPageShell';
import { Text } from '@/components/shared/Text';
import { useAdminOrders } from '@/hooks/admin/useAdminOrders';

export function AdminOrdersScreen() {
    const { orders, isLoading } = useAdminOrders();

    return (
        <AdminPageShell activeSection="orders" title="Управление заказами">
            {isLoading
                ? <Text size={16} className="text-gray-500">Загрузка...</Text>
                : <AdminOrdersTable orders={orders} />}
        </AdminPageShell>
    );
}
