"use client";

import React from 'react';
import Image from 'next/image';
import NextLink from 'next/link';
import { useRouter } from 'next/navigation';
import { Swiper, SwiperSlide } from 'swiper/react';
import { Pagination } from 'swiper/modules';
import 'swiper/css';
import 'swiper/css/pagination';
import { Text } from './Text';
import { CatalogQuantityControl } from './CatalogQuantityControl';
import { useCatalogCartItem } from '@/hooks/cart/useCatalogCartItem';
import { useMobileCatalogCardVideo } from '@/hooks/catalog/useMobileCatalogCardVideo';

interface MobileProductCardProps {
    id: number;
    title: React.ReactNode;
    price: number;
    oldPrice?: number;
    imageLeft: string;
    imageRight: string;
    videoSrc?: string;
    videoPoster?: string;
    mobileSliderImages?: string[];
    priority: number;
    cartTitle?: string;
}

export const MobileProductCard: React.FC<MobileProductCardProps> = ({
    id, title, price, oldPrice, imageLeft, imageRight, videoSrc, videoPoster, mobileSliderImages, priority, cartTitle,
}) => {
    const router = useRouter();
    const {
        videoRef,
        containerRef,
        progress,
        actuallyLoadVideo,
        showVideo,
        handleCanPlayThrough,
        handleProgress,
        handlePlaying,
        handlePlaybackInterruption,
        handleError,
    } = useMobileCatalogCardVideo({ productId: id, priority, videoSrc });
    const {
        quantity: catalogQuantity,
        addToCart: handleAddToCart,
        decreaseQuantity: handleDecreaseQuantity,
        increaseQuantity: handleIncreaseQuantity,
    } = useCatalogCartItem({
        productId: id,
        title,
        cartTitle,
        price,
        image: imageLeft || imageRight || '/landing-bg.webp',
    });

    const handleGearClick = (event: React.MouseEvent) => {
        event.preventDefault();
        event.stopPropagation();
        router.push(`/constructor?productId=${id}`);
    };

    const sliderImages = mobileSliderImages && mobileSliderImages.length > 0
        ? mobileSliderImages
        : [imageRight, imageLeft, imageRight];
    const leftImage = videoPoster || imageLeft;

    return (
        <>
            <div
                className="block w-full mb-[clamp(80px,18vw,115px)]"
                data-catalog-layout="mobile"
                data-catalog-product-id={id}
            >
                {/* Top Images Section */}
                <div className="flex px-[clamp(16px,3.75vw,24px)] gap-[clamp(16px,3.75vw,24px)]">

                    {/* Left Column (Icon + Tall Image/Video) */}
                    <div className="flex items-start relative">
                        {/* Gear Icon */}
                        <div
                            onClick={handleGearClick}
                            className="absolute top-1/2 w-[32px] h-[42px] -translate-y-1/2 flex items-center justify-center z-10 overflow-visible cursor-pointer hover:opacity-80 transition-opacity"
                            style={{ left: 'calc(clamp(16px, 3.75vw, 24px) * -1)' }}
                        >
                            <div
                                className="w-[32px] h-[30px] rounded-r-full rounded-l-none bg-[#F2F2F2] flex items-center justify-center"
                                style={{ filter: 'drop-shadow(0 1.785px 3.57px rgba(0, 0, 0, 0.25))' }}
                            >
                                <Image src="/mob_icon.svg" alt="Gear" width={16} height={16} className="h-[16px] w-[16px] object-contain" />
                            </div>
                        </div>
                        {/* Tall Left Image / Video */}
                        <NextLink href={`/product/${id}`} ref={containerRef} className="w-[clamp(110px,24vw,154px)] aspect-[1/2.8] bg-[#F2F2F2] relative rounded-md overflow-hidden shrink-0 ml-[8px]">
                            {/* Poster / default image */}
                            <Image
                                src={leftImage}
                                alt="Left container"
                                fill
                                priority={priority <= 4}
                                className={`object-cover object-top transition-opacity duration-500 ${showVideo ? 'opacity-0' : 'opacity-100'}`}
                            />

                            {/* Video loading progress bar */}
                            {videoSrc && progress < 100 && progress > 0 && actuallyLoadVideo && (
                                <div className="absolute top-2 left-2 right-2 h-[3px] bg-white/30 rounded-full overflow-hidden z-20">
                                    <div
                                        className="h-full bg-white transition-all duration-300"
                                        style={{ width: `${progress}%` }}
                                    />
                                </div>
                            )}

                            {/* Video — preloaded silently, shown once played */}
                            {videoSrc && (
                                <video
                                    ref={videoRef}
                                    src={actuallyLoadVideo ? videoSrc : undefined}
                                    poster={leftImage}
                                    loop
                                    className={`absolute inset-0 w-full h-full bg-transparent object-cover object-top transition-opacity duration-150 ${showVideo ? 'opacity-100' : 'opacity-0'}`}
                                    style={{ height: '101%', top: '-1px', objectPosition: 'top center' }}
                                    muted
                                    playsInline
                                    preload={actuallyLoadVideo ? "auto" : "none"}
                                    onCanPlay={handleCanPlayThrough}
                                    onLoadedData={handleCanPlayThrough}
                                    onCanPlayThrough={handleCanPlayThrough}
                                    onProgress={handleProgress}
                                    onPlaying={handlePlaying}
                                    onPause={handlePlaybackInterruption}
                                    onWaiting={handlePlaybackInterruption}
                                    onStalled={handlePlaybackInterruption}
                                    onEnded={handlePlaybackInterruption}
                                    onError={handleError}
                                />
                            )}

                        </NextLink>
                    </div>

                    {/* Right Column (Wide Slider Image + Text under it) */}
                    <div className="flex-1 flex flex-col min-w-0">
                        {/* Slider */}
                        <NextLink href={`/product/${id}`} className="w-full h-[clamp(273px,61vw,390px)] relative rounded-md overflow-hidden mb-[clamp(12px,2.5vw,16px)] shrink-0">
                            <Swiper
                                modules={[Pagination]}
                                pagination={{ clickable: true }}
                                className="w-full h-full"
                            >
                                {sliderImages.map((img, i) => (
                                    <SwiperSlide key={i}>
                                        <Image src={img} alt={`Slider Image ${i + 1}`} fill className="object-cover object-top" />
                                    </SwiperSlide>
                                ))}
                            </Swiper>
                        </NextLink>

                        {/* Text (Title, Price) */}
                        <div className="flex flex-col items-center w-full px-0.5">
                            <NextLink href={`/product/${id}`} className="leading-snug text-center w-full">
                                <Text size="clamp(10px, 2.35vw, 15px)" className="font-semibold text-black uppercase tracking-tight text-center block w-full">
                                    {title}
                                </Text>
                            </NextLink>

                            <div className="mt-[6px] flex items-center justify-center gap-[10px] w-full">
                                <CatalogQuantityControl
                                    quantity={catalogQuantity}
                                    onAdd={handleAddToCart}
                                    onDecrease={handleDecreaseQuantity}
                                    onIncrease={handleIncreaseQuantity}
                                />
                                <NextLink href={`/product/${id}`} className="flex flex-row items-center gap-[3px]">
                                    <Text size="clamp(11px, 2.5vw, 16px)" className="text-black font-medium text-left">{price} ₽</Text>
                                    {oldPrice && (
                                        <Text size="clamp(11px, 2.5vw, 16px)" className="text-[#A0A0A0] line-through text-left">{oldPrice} ₽</Text>
                                    )}
                                </NextLink>
                            </div>
                        </div>
                    </div>

                </div>
            </div>
        </>
    );
};

