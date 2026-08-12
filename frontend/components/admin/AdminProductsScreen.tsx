'use client';

import NextLink from 'next/link';

import { AdminPageShell } from '@/components/admin/AdminPageShell';
import { AdminProductsTable } from '@/components/admin/AdminProductsTable';
import { Text } from '@/components/shared/Text';
import { useAdminProducts } from '@/hooks/admin/useAdminProducts';

const createProductAction = (
    <NextLink href="/admin/products/new">
        <button className="bg-black text-white px-6 py-3 rounded-md hover:bg-gray-800 transition">
            Добавить товар
        </button>
    </NextLink>
);

export function AdminProductsScreen() {
    const { products, isLoading, deleteProduct } = useAdminProducts();

    return (
        <AdminPageShell
            activeSection="products"
            title="Управление товарами"
            action={createProductAction}
        >
            {isLoading
                ? <Text size={16} className="text-gray-500">Загрузка...</Text>
                : <AdminProductsTable products={products} onDelete={deleteProduct} />}
        </AdminPageShell>
    );
}
