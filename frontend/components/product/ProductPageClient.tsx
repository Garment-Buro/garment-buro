"use client";

import 'swiper/css';
import 'swiper/css/pagination';
import 'swiper/css/navigation';

import { Container } from '@/components/shared/Container';
import { useProductPage } from '@/hooks/product/useProductPage';
import type { ProductData } from '@/lib/products/types';

import { ProductDesktopLayout } from './ProductDesktopLayout';
import { ProductMobileLayout } from './ProductMobileLayout';
import { ProductSizeChartModal, ProductWaitlistModal } from './ProductModals';

export type { ProductData } from '@/lib/products/types';

type ProductPageClientProps = {
    initialProduct: ProductData;
    initialProducts?: ProductData[];
};

export default function ProductPageClient({
    initialProduct,
    initialProducts = [],
}: ProductPageClientProps) {
    const productPage = useProductPage(initialProduct, initialProducts);
    if (!productPage.product) return null;

    return (
        <Container size="full" className="pt-0 pb-[100px] min-h-screen relative px-[20px] lg:px-0 lg:pr-[40px] animate-fade-in transition-opacity duration-500 bg-[#F2F2F2]">
            <ProductDesktopLayout page={productPage} />
            <ProductMobileLayout page={productPage} />
            <ProductSizeChartModal
                product={productPage.product}
                isOpen={productPage.showSizeChart}
                onClose={() => productPage.setShowSizeChart(false)}
            />
            <ProductWaitlistModal page={productPage} />
        </Container>
    );
}
