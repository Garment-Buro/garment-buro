"use client";

import type { CSSProperties } from 'react';
import Image from 'next/image';
import NextLink from 'next/link';
import { Navigation } from 'swiper/modules';
import { Swiper, SwiperSlide } from 'swiper/react';

import { AppIcon } from '@/components/icons/AppIcon';
import { CartActionBar } from '@/components/cart/CartActionBar';
import { DecryptedText } from '@/components/shared/DecryptedText';
import { MobileProductCard } from '@/components/shared/MobileProductCard';
import { ProductTitle } from '@/components/shared/ProductTitle';
import { Text } from '@/components/shared/Text';
import type { ProductPageViewModel } from '@/hooks/product/useProductPage';
import {
    PRODUCT_MOBILE_FIRST_BLOCK_TOP_OFFSET,
    PRODUCT_MOBILE_HEADER_FOOTPRINT,
    PRODUCT_MOBILE_HEADER_TOP_OFFSET,
    PRODUCT_MOBILE_HERO_GAP,
    PRODUCT_MOBILE_HERO_TOP_COMPENSATION,
} from '@/lib/products/constants';
import {
    getPrimaryProductImage,
    getProductCartImage,
    parseProductMediaList,
} from '@/lib/products/utils/product';

export const ProductMobileLayout = ({ page }: { page: ProductPageViewModel }) => {
    const {
        product,
        loadedImagesCount,
        setLoadedImagesCount,
        selectedColor,
        setSelectedColor,
        selectedSize,
        setSelectedSize,
        setShowSizeChart,
        relatedSlideIndex,
        setRelatedSlideIndex,
        hasScrolled,
        currentProductCartItem,
        currentCartColor,
        normalizedProductDescription,
        reviewImagesToRender,
        nextProducts,
        relatedProductPages,
        colorOptions,
        sizesForSelectedColor,
        currentStock,
        mobileSliderImages,
        handleProductBack,
        handleMobileAddClick,
        handleMobileEditClick,
        handleMobileBuyClick,
    } = page;

    if (!product) return null;

    return (
        <div className="flex flex-col lg:hidden w-full font-manrope relative">
            <button
                type="button"
                onClick={handleProductBack}
                className="absolute left-[-8px] z-[120] flex h-[40px] w-[40px] items-center justify-center p-0 transition hover:opacity-70"
                style={{
                    top: `calc(clamp(70px, 18.92vw, 121px) + ${PRODUCT_MOBILE_HEADER_TOP_OFFSET} - 18px)`,
                }}
                aria-label="Назад"
            >
                <Image src="/back_icon_item.svg" alt="" width={18} height={11} className="h-[11px] w-[18px] object-contain" />
            </button>

            <section
                className="product-mobile-hero flex min-h-[100dvh] w-full flex-col justify-between gap-[clamp(24px,9.73vw,36px)]"
                style={{
                    paddingTop: `calc(${PRODUCT_MOBILE_HEADER_FOOTPRINT} + ${PRODUCT_MOBILE_HERO_GAP} + ${PRODUCT_MOBILE_HERO_TOP_COMPENSATION} + ${PRODUCT_MOBILE_FIRST_BLOCK_TOP_OFFSET})`,
                    boxSizing: 'border-box',
                }}
            >
                <div className="flex w-full justify-between items-center">
                    <div className="flex items-start z-10">
                        <div className="flex items-center gap-[clamp(11px,2.97vw,19px)]">
                            {sizesForSelectedColor.map(({ size, stock }) => (
                                <button
                                    key={size}
                                    onClick={() => setSelectedSize(size)}
                                    className={`text-[20px] font-manrope font-light flex items-center justify-center transition-all w-[clamp(40px,10.81vw,69px)] h-[clamp(32px,8.65vw,55px)] ${stock === 0 ? 'text-[#BEBEBE] cursor-not-allowed' : 'text-black'}`}
                                    style={selectedSize === size ? {
                                        background: 'linear-gradient(180deg, #F3F3F3 -0.72%, #E7E7E7 100.37%)',
                                        boxShadow: '0 2px 4px 0 rgba(0, 0, 0, 0.25) inset',
                                        borderRadius: '4px',
                                    } : {}}
                                >
                                    {size}
                                </button>
                            ))}
                        </div>
                        <button onClick={() => setShowSizeChart(true)} className="ml-[6px] mt-[-7px] flex h-[14px] w-[14px] shrink-0 items-center justify-center p-0 text-black" aria-label="Показать размеры">
                            <AppIcon name="info" width={14} height={14} className="h-[14px] w-[14px]" />
                        </button>
                    </div>

                    <div className="w-[clamp(90px,24.32vw,156px)] h-[clamp(300px,81.08vw,520px)] bg-transparent rounded-md overflow-hidden relative shrink-0">
                        {product.mobile_size_chart_first ? (
                            <Image
                                src={product.mobile_size_chart_first}
                                alt="Size Chart First"
                                fill
                                priority
                                loading="eager"
                                fetchPriority="high"
                                sizes="(max-width: 1023px) 24vw, 156px"
                                className="object-contain object-top"
                                style={{ objectPosition: 'top center' }}
                            />
                        ) : (
                            <Image
                                src={mobileSliderImages[0] || '/landing-bg.webp'}
                                alt="Model Right"
                                fill
                                priority
                                loading="eager"
                                fetchPriority="high"
                                sizes="(max-width: 1023px) 24vw, 156px"
                                className="object-contain object-top"
                                style={{ objectPosition: 'top center' }}
                            />
                        )}
                    </div>
                </div>

                <div className="flex w-full justify-between items-stretch gap-[clamp(25px,6.76vw,43px)]">
                    <div className="w-[clamp(185px,50vw,320px)] h-[clamp(270px,72.97vw,467px)] bg-transparent relative rounded-md overflow-hidden shrink-0">
                        <Image
                            src={product.mobile_card_image || product.image_left || '/landing-bg.webp'}
                            alt="Mobile First"
                            fill
                            priority
                            loading="eager"
                            fetchPriority="high"
                            sizes="(max-width: 1023px) 50vw, 320px"
                            className="object-cover object-top"
                            style={{ objectPosition: 'top center' }}
                            onLoad={() => setLoadedImagesCount(previous => Math.max(previous, 1))}
                        />
                    </div>

                    <div className="flex min-w-0 flex-1 flex-col justify-between font-manrope h-[clamp(270px,72.97vw,467px)]">
                        <div className="pt-[30px]">
                            <Text size="clamp(11px, 2.97vw, 19px)" className="leading-snug text-black">
                                <ProductTitle title={product.title} />
                            </Text>
                            <div
                                className="mt-[30px]"
                                style={{
                                    color: '#2D2D2D',
                                    fontFamily: 'var(--font-manrope), Manrope, sans-serif',
                                    fontSize: 'clamp(14px, 3.78vw, 24px)',
                                    fontStyle: 'normal',
                                    fontWeight: 400,
                                    lineHeight: 'normal',
                                }}
                            >
                                <DecryptedText animateOn="none" text={`${product.price.toLocaleString('ru-RU')} ₽`} />
                            </div>
                        </div>

                        <div className="text-[clamp(9px,2.43vw,16px)] leading-relaxed text-black whitespace-pre-wrap">
                            {normalizedProductDescription || "Рекомендации по размерам...\nS: 160-170см\nM: 171-177см"}
                        </div>
                    </div>
                </div>
            </section>

            {colorOptions.length > 0 && (
                <div className="mx-[-20px] px-[5px]" style={{ paddingTop: 20, paddingBottom: 20 }}>
                    <div className="flex gap-[10px] overflow-x-auto scrollbar-hide">
                        {colorOptions.map(({ label, hex }) => {
                            const isActive = selectedColor === label;
                            const preview = product.variants?.find(variant => variant.color === label)?.preview_image;
                            return (
                                <button
                                    key={label}
                                    onClick={() => setSelectedColor(label)}
                                    style={{
                                        width: 'clamp(45px, 12.16vw, 78px)',
                                        height: 'clamp(45px, 12.16vw, 78px)',
                                        minWidth: 'clamp(45px, 12.16vw, 78px)',
                                        borderRadius: 3,
                                        border: isActive ? '1px solid #97969B' : '1px solid transparent',
                                        padding: 0,
                                        overflow: 'hidden',
                                        cursor: 'pointer',
                                        position: 'relative',
                                        background: preview ? 'transparent' : hex,
                                        flexShrink: 0,
                                    }}
                                >
                                    {preview && <Image src={preview} alt={label} fill className="object-cover object-top" />}
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}

            <div className="w-screen relative left-1/2 -translate-x-1/2 aspect-square bg-transparent overflow-hidden">
                <Swiper modules={[Navigation]} navigation style={{ '--swiper-navigation-color': '#fff', '--swiper-navigation-size': '16px' } as CSSProperties} className="w-full h-full">
                    {mobileSliderImages.map((image, index) => (
                        <SwiperSlide key={index}>
                            {index <= loadedImagesCount && (
                                <Image
                                    src={image}
                                    alt={`Gallery ${index}`}
                                    fill
                                    priority={index === 0}
                                    className="object-cover object-top"
                                    style={{ objectPosition: 'top center' }}
                                    onLoad={() => setLoadedImagesCount(previous => Math.max(previous, index + 2))}
                                />
                            )}
                        </SwiperSlide>
                    ))}
                </Swiper>
            </div>

            <CartActionBar
                visible={hasScrolled}
                title={currentProductCartItem?.title || product.title}
                color={currentProductCartItem?.color || currentCartColor}
                price={currentProductCartItem?.price || product.price}
                image={getProductCartImage(product)}
                cartItemId={currentProductCartItem?.id}
                usePreferredCartItemOnly
                showAddProductCard
                disabled={currentStock === 0}
                onAdd={handleMobileAddClick}
                onEdit={handleMobileEditClick}
                onBuy={handleMobileBuyClick}
            />

            <div className="mt-[20px] mx-[-20px] px-[5px] flex justify-center">
                <div className="w-full h-[clamp(120px,31vw,198px)] rounded-[10px] p-[4px] overflow-x-auto overflow-y-hidden scrollbar-hide touch-pan-x" style={{ background: '#FFF' }}>
                    <div className="flex h-full min-w-max items-center gap-[clamp(4px,1.08vw,7px)]">
                        {reviewImagesToRender.map((image, index) => (
                            <div
                                key={`review-preview-${index}`}
                                className={`relative h-full aspect-square shrink-0 overflow-hidden ${index === 0 ? 'rounded-l-[6px]' : ''} ${index === reviewImagesToRender.length - 1 ? 'rounded-r-[6px]' : ''}`}
                            >
                                <Image src={image} alt={`Отзыв ${index + 1}`} fill className="object-cover object-top" />
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {relatedProductPages.length > 0 && (
                <div className="mt-[20px] mx-[-20px] px-[5px] flex justify-center">
                    <div
                        className="w-full h-[clamp(450px,121.622vw,779px)] rounded-[10px] px-[clamp(16px,4.32vw,28px)] py-[clamp(10px,2.7vw,17px)] flex flex-col"
                        style={{
                            background: 'linear-gradient(90deg, #FFF 0%, #FDFDFD 109.77%)',
                            boxShadow: 'inset 0 2px 4px rgba(0, 0, 0, 0.15)',
                        }}
                    >
                        <Text size="clamp(12px,3.24vw,21px)" className="font-medium" style={{ color: 'rgba(136, 135, 135, 0.60)' }}>
                            похожие
                        </Text>

                        <div className="mt-[clamp(20px,5.4vw,35px)] flex-1 overflow-hidden">
                            <Swiper
                                slidesPerView={1}
                                className="w-full h-full"
                                onSlideChange={swiper => setRelatedSlideIndex(swiper.activeIndex)}
                                onSwiper={swiper => setRelatedSlideIndex(swiper.activeIndex)}
                            >
                                {relatedProductPages.map((products, pageIndex) => (
                                    <SwiperSlide key={`related-page-${pageIndex}`}>
                                        <div className="grid grid-cols-3 gap-y-[clamp(20px,5.4vw,35px)] gap-x-[clamp(10px,2.7vw,17px)] justify-items-center">
                                            {products.map(item => (
                                                <NextLink
                                                    key={`related-product-${item.id}`}
                                                    href={`/product/${item.id}`}
                                                    className="w-[clamp(100px,27.027vw,173px)] flex flex-col items-center"
                                                >
                                                    <div className="relative h-[clamp(127px,34.324vw,220px)] w-[clamp(100px,27.027vw,173px)] overflow-hidden">
                                                        <Image src={getPrimaryProductImage(item)} alt={item.title} fill className="object-cover object-top" />
                                                    </div>
                                                    <Text size="clamp(8px,2.16vw,14px)" className="mt-[clamp(14px,3.78vw,24px)] text-[#545454] text-center font-medium leading-[88%] max-h-[clamp(14px,3.78vw,24px)] overflow-hidden">
                                                        {item.title}
                                                    </Text>
                                                    <Text size="clamp(10px,2.7vw,17px)" className="mt-[clamp(9px,2.43vw,16px)] text-[#242323] text-center font-medium">
                                                        {item.price.toLocaleString('ru-RU')} ₽
                                                    </Text>
                                                </NextLink>
                                            ))}
                                            {products.length < 6 && Array.from({ length: 6 - products.length }).map((_, emptyIndex) => (
                                                <div key={`related-empty-${pageIndex}-${emptyIndex}`} className="w-[clamp(100px,27.027vw,173px)]" />
                                            ))}
                                        </div>
                                    </SwiperSlide>
                                ))}
                            </Swiper>
                        </div>

                        {relatedProductPages.length > 1 && (
                            <div className="mt-[clamp(8px,2.16vw,14px)] flex items-center justify-center gap-[clamp(10px,2.7vw,17px)]">
                                {relatedProductPages.map((_, dotIndex) => (
                                    <span
                                        key={`related-dot-${dotIndex}`}
                                        className="w-[clamp(4px,1.08vw,7px)] h-[clamp(4px,1.08vw,7px)] rounded-full"
                                        style={{ backgroundColor: relatedSlideIndex === dotIndex ? '#9D9D9D' : '#D9D9D9' }}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {nextProducts.length > 0 && (
                <div className="mt-[30px] mx-[-20px]">
                    {nextProducts.map((nextProduct, index) => (
                        <div key={`next-product-${nextProduct.id}-${index}`} className="relative z-[70]">
                            <MobileProductCard
                                id={nextProduct.id}
                                title={<ProductTitle title={nextProduct.title} />}
                                price={nextProduct.price}
                                oldPrice={nextProduct.old_price}
                                imageLeft={nextProduct.mobile_card_image || nextProduct.image_left || '/landing-bg.webp'}
                                imageRight={nextProduct.image_right || '/landing-bg.webp'}
                                videoSrc={nextProduct.desktop_video || nextProduct.video_src}
                                videoPoster={nextProduct.mobile_video_poster}
                                mobileSliderImages={nextProduct.mobile_slider_images ? parseProductMediaList(nextProduct.mobile_slider_images) : undefined}
                                priority={40 + index}
                                cartTitle={nextProduct.title}
                            />
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
