"use client";

import Image from 'next/image';

import { DecryptedText } from '@/components/shared/DecryptedText';
import { ProductTitle } from '@/components/shared/ProductTitle';
import { Text } from '@/components/shared/Text';
import type { ProductPageViewModel } from '@/hooks/product/useProductPage';

export const ProductDesktopLayout = ({ page }: { page: ProductPageViewModel }) => {
    const {
        product,
        desktopSliderImages,
        loadedImagesCount,
        setLoadedImagesCount,
        activeDesktopImg,
        normalizedProductDescription,
        colorOptions,
        selectedColor,
        setSelectedColor,
        sizesForSelectedColor,
        selectedSize,
        setSelectedSize,
        currentStock,
        setShowWaitlistForm,
        addProductToCart,
        showSizeChart,
        setShowSizeChart,
    } = page;

    if (!product) return null;

    return (
        <div className="hidden items-start gap-[60px] lg:flex lg:flex-row">
            <div className="sticky top-0 z-0 -ml-[30px] flex h-screen w-[220px] shrink-0 flex-col pl-[20px]">
                <div className="mt-[100px] flex w-[130px] flex-col gap-4 p-4 text-black">
                    {desktopSliderImages.map((image, index) => (
                        <div
                            key={index}
                            onClick={() => document.getElementById(`desktop-img-${index}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                            className={`relative mx-auto h-[80px] w-[60px] cursor-pointer overflow-hidden bg-[#E5E5E5] transition-all ${activeDesktopImg === index ? 'border-[1.5px] border-black opacity-100' : 'opacity-60 hover:opacity-100'}`}
                        >
                            <Image src={image} alt={`Thumb ${index}`} fill className="object-cover object-top" />
                        </div>
                    ))}
                </div>
            </div>

            <div className="flex flex-1 flex-col gap-2 lg:pt-[100px]">
                {desktopSliderImages.map((image, index) => (
                    <div id={`desktop-img-${index}`} data-index={index} key={index} className="desktop-slider-img relative aspect-4/5 w-full overflow-hidden">
                        {index <= loadedImagesCount && (
                            <Image
                                src={image}
                                alt={`${product.title} ${index}`}
                                fill
                                priority={index === 0}
                                className="object-contain object-top"
                                style={{ objectPosition: 'top center' }}
                                onLoad={() => setLoadedImagesCount(previous => Math.max(previous, index + 2))}
                            />
                        )}
                    </div>
                ))}
            </div>

            <div className="scrollbar-hide flex w-full shrink-0 flex-col pb-10 font-manrope lg:sticky lg:top-[100px] lg:h-[calc(100vh-95px)] lg:w-[380px] lg:overflow-y-auto">
                <Text as="h1" size={24} className="mt-4 mb-8 leading-tight lg:mt-0">
                    <ProductTitle title={product.title} />
                </Text>
                <Text size={24} className="mb-10">
                    <DecryptedText animateOn="none" text={`${product.price.toLocaleString('ru-RU')} ₽`} />
                </Text>

                <div className="mb-10 flex flex-col gap-6 whitespace-pre-wrap text-[11px] leading-relaxed text-black lg:text-[14px]">
                    {product.description ? (
                        <p>{normalizedProductDescription}</p>
                    ) : (
                        <div>
                            <p>Состав: 100% хлопок</p>
                            <p>Материал: футер 3-х нитка, без начеса</p>
                            <p>Плотность: 450 г</p>
                        </div>
                    )}
                </div>

                {colorOptions.length > 0 && (
                    <div className="mb-8">
                        <Text size={13} className="mb-4">Цвет: {selectedColor}</Text>
                        <div className="flex gap-4">
                            {colorOptions.map(({ label, hex }) => (
                                <button
                                    key={label}
                                    onClick={() => setSelectedColor(label)}
                                    className={`flex h-[40px] w-[40px] items-center justify-center rounded-full border transition-colors ${selectedColor === label ? 'border-black' : 'border-transparent'}`}
                                >
                                    <div className="h-[32px] w-[32px] rounded-full border border-black/10" style={{ backgroundColor: hex }} />
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {sizesForSelectedColor.length > 0 && (
                    <div className="mb-8">
                        <div className="flex flex-wrap items-center gap-[40px] px-2">
                            {sizesForSelectedColor.map(({ size, stock }) => (
                                <button
                                    key={size}
                                    onClick={() => setSelectedSize(size)}
                                    className={`flex items-center justify-center px-[12px] py-[4px] font-manrope text-[20px] font-light transition-all ${stock === 0 ? 'cursor-not-allowed text-[#BEBEBE]' : 'cursor-pointer text-black'}`}
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
                        {currentStock < 5 && currentStock > 0 && (
                            <Text size={12} className="mt-2 text-red-500">Осталось всего {currentStock} шт!</Text>
                        )}
                    </div>
                )}

                <button
                    onClick={() => currentStock === 0 ? setShowWaitlistForm(true) : addProductToCart(1)}
                    className="mb-10 flex h-[55px] w-[220px] cursor-pointer items-center justify-center rounded-[12px] border border-white/80 bg-[linear-gradient(180deg,#FFFFFF_0%,#F0F0F0_100%)] font-manrope text-[16px] text-black shadow-[0_2px_10px_rgba(0,0,0,0.05)] transition-transform active:translate-y-px md:min-h-[55px]"
                >
                    {currentStock === 0 ? 'сообщить мне' : 'добавить в корзину'}
                </button>

                <div className="border-t border-black/10 pt-4">
                    <button className="flex cursor-pointer items-center gap-2 font-manrope text-[13px]" onClick={() => setShowSizeChart(!showSizeChart)}>
                        Размерная сетка
                        <svg width="10" height="6" viewBox="0 0 10 6" fill="none" className={`transition-transform duration-300 ${showSizeChart ? 'rotate-180' : ''}`}>
                            <path d="M1 1L5 5L9 1" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </button>
                    <div className={`mt-6 overflow-hidden transition-all ${showSizeChart ? 'max-h-[800px] opacity-100' : 'max-h-0 opacity-0'}`}>
                        <div className="flex w-full flex-col gap-6">
                            <div className="relative flex w-full items-center justify-center">
                                <Image src={product.size_chart_img_1 || '/setka_1.svg'} alt="Size Diagram" width={300} height={250} className="h-auto w-full" />
                            </div>
                            <div className="relative flex w-full items-center justify-center">
                                <Image src={product.size_chart_img_2 || '/setka_2.svg'} alt="Size Table" width={300} height={150} className="h-auto w-full" />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
