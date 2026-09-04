import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import ProductPageClient from '@/components/product/ProductPageClient';
import { getServerProduct, getServerProducts } from '@/lib/api/products.server';
import { PUBLIC_CATALOG_ENABLED } from '@/lib/catalog/public';
import { parseProductId } from '@/lib/products/utils/productId';

type ProductPageProps = {
    params: Promise<{
        id: string;
    }>;
};

// Next.js requires route configuration exports to be statically analyzable.
export const revalidate = 60;

export async function generateStaticParams() {
    if (!PUBLIC_CATALOG_ENABLED) return [];
    try {
        const products = await getServerProducts();
        return products.map(product => ({ id: String(product.id) }));
    } catch {
        return [];
    }
}

export async function generateMetadata({ params }: ProductPageProps): Promise<Metadata> {
    if (!PUBLIC_CATALOG_ENABLED) return { title: 'Страница недоступна', robots: { index: false } };
    const { id: rawId } = await params;
    const id = parseProductId(rawId);
    if (!id) return { title: 'Товар не найден' };

    const product = await getServerProduct(id);
    if (!product) return { title: 'Товар не найден' };

    return {
        title: product.title,
        description: product.description?.slice(0, 160) || `Купить ${product.title} в Garment Buro.`,
    };
}

export default async function ProductPage({ params }: ProductPageProps) {
    if (!PUBLIC_CATALOG_ENABLED) notFound();
    const { id: rawId } = await params;
    const id = parseProductId(rawId);
    if (!id) notFound();

    const [product, products] = await Promise.all([
        getServerProduct(id),
        getServerProducts().catch(() => []),
    ]);

    if (!product) notFound();

    return (
        <ProductPageClient
            key={product.id}
            initialProduct={product}
            initialProducts={products}
        />
    );
}
