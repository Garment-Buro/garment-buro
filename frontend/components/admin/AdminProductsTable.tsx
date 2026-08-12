import NextLink from 'next/link';

import type { AdminProductSummary } from '@/lib/products/types';

type AdminProductsTableProps = {
    products: AdminProductSummary[];
    onDelete: (productId: number) => void;
};

export function AdminProductsTable({ products, onDelete }: AdminProductsTableProps) {
    return (
        <div className="bg-white rounded-md shadow-sm border border-black/10 overflow-hidden text-black">
            <table className="w-full text-left border-collapse">
                <thead>
                    <tr className="bg-gray-50 border-b border-black/10">
                        <th className="p-4 font-semibold">ID</th>
                        <th className="p-4 font-semibold">Название</th>
                        <th className="p-4 font-semibold">Цена</th>
                        <th className="p-4 font-semibold">Активен</th>
                        <th className="p-4 font-semibold text-right">Действия</th>
                    </tr>
                </thead>
                <tbody>
                    {products.length > 0 ? products.map((product) => (
                        <tr key={product.id} className="border-b border-black/5 hover:bg-gray-50">
                            <td className="p-4">{product.id}</td>
                            <td className="p-4">{product.title}</td>
                            <td className="p-4">{product.price} ₽</td>
                            <td className="p-4">{product.is_active ? 'Да' : 'Нет'}</td>
                            <td className="p-4 text-right">
                                <NextLink href={`/admin/products/${product.id}/edit`}>
                                    <button className="text-blue-600 hover:text-blue-800 mr-4">Ред.</button>
                                </NextLink>
                                <button
                                    type="button"
                                    onClick={() => onDelete(product.id)}
                                    className="text-red-500 hover:text-red-700"
                                >
                                    Удалить
                                </button>
                            </td>
                        </tr>
                    )) : (
                        <tr>
                            <td colSpan={5} className="p-6 text-center text-gray-500">Нет товаров</td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
}
