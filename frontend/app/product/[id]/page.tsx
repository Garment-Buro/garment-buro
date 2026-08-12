import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import ProductPageClient from '@/components/product/ProductPageClient';
import { getServerProduct, getServerProducts } from '@/lib/api/products.server';
import { parseProductId } from '@/lib/products/utils/productId';

type ProductPageProps = {
    params: Promise<{
        id: string;
    }>;
};

// Next.js requires route configuration exports to be statically analyzable.
export const revalidate = 60;

export async function generateStaticParams() {
    try {
        const products = await getServerProducts();
        return products.map(product => ({ id: String(product.id) }));
    } catch {
        return [];
    }
}

export async function generateMetadata({ params }: ProductPageProps): Promise<Metadata> {
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
