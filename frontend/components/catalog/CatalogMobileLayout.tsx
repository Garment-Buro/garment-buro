import { MobileProductCard } from '@/components/shared/MobileProductCard';
import { ProductTitle } from '@/components/shared/ProductTitle';
import { parseCatalogMediaList } from '@/lib/catalog/utils/catalog';
import type { CatalogProduct } from '@/lib/products/types';

export const CatalogMobileLayout = ({ products }: { products: CatalogProduct[] }) => (
    <div className="flex w-full flex-col bg-[#F2F2F2] pt-[clamp(120px,32.4vw,207px)] pb-[40px] md:hidden">
        {products.map((product, index) => (
            <div key={product.id} className="relative z-[70]">
                <MobileProductCard
                    id={product.id}
                    title={<ProductTitle title={product.title} />}
                    price={product.price}
                    oldPrice={product.old_price}
                    imageLeft={product.mobile_card_image || product.image_left || '/landing-bg.webp'}
                    imageRight={product.image_right || '/landing-bg.webp'}
                    videoSrc={product.desktop_video || product.video_src}
                    videoPoster={product.mobile_video_poster}
                    mobileSliderImages={parseCatalogMediaList(product.mobile_slider_images)}
                    priority={index + 1}
                    cartTitle={product.title}
                />
            </div>
        ))}
    </div>
);
