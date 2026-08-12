"use client";

import React from 'react';
import Image from 'next/image';
import NextLink from 'next/link';
import { Text } from './Text';
import { CatalogQuantityControl } from './CatalogQuantityControl';
import { useCatalogCartItem } from '@/hooks/cart/useCatalogCartItem';
import { useDesktopCatalogCardVideo } from '@/hooks/catalog/useDesktopCatalogCardVideo';

interface ProductCardProps {
    id: number;
    title: React.ReactNode;
    price: number;
    oldPrice?: number;
    videoSrc?: string;
    videoPoster?: string;
    priority: number;
    cartTitle?: string;
}

export const ProductCard: React.FC<ProductCardProps> = ({ id, title, price, oldPrice, videoSrc, videoPoster, priority, cartTitle }) => {
    const {
        videoRef,
        containerRef,
        shouldLoad,
        showVideo,
        handleMouseEnter,
        handleMouseLeave,
        handleCanPlayThrough,
        handleProgress,
        handlePlaybackInterruption,
        handlePlaying,
        handleEnded,
        handlePause,
        handleError,
    } = useDesktopCatalogCardVideo({ productId: id, priority, videoSrc });
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
        image: videoPoster || '/landing-bg.webp',
    });

    return (
        <div
            className="w-[200px] h-[465px] flex flex-col"
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            data-catalog-layout="desktop"
            data-catalog-product-id={id}
        >
            {/* Video / Poster Container */}
            <div ref={containerRef} className="w-[158px] h-[350px] mx-auto relative overflow-hidden rounded-[2px] bg-[#F2F2F2]">
                <NextLink
                    href={`/constructor?productId=${id}`}
                    className="absolute left-[-15px] top-1/2 z-30 flex h-[40px] w-[30px] -translate-y-1/2 items-center justify-center overflow-visible transition hover:opacity-80"
                    aria-label="Перейти в конструктор"
                >
                    <div
                        className="flex h-[28px] w-[30px] items-center justify-center rounded-r-full bg-[#F2F2F2]"
                        style={{ filter: 'drop-shadow(0 1.785px 3.57px rgba(0, 0, 0, 0.25))' }}
                    >
                        <Image src="/mob_icon.svg" alt="" width={15} height={15} className="h-[15px] w-[15px] object-contain" />
                    </div>
                </NextLink>

                <NextLink href={`/product/${id}`} className="relative block h-full w-full">
                    {/* Poster image — visible until video plays */}
                    {videoPoster && (
                        <Image
                            src={videoPoster}
                            alt=""
                            fill
                            priority={priority <= 4}
                            className={`object-cover object-top transition-opacity duration-150 ${showVideo ? 'opacity-0' : 'opacity-100'}`}
                        />
                    )}

                    {/* Video — preloaded silently, shown on hover once ready */}
                    {videoSrc && (
                        <video
                            ref={videoRef}
                            src={shouldLoad ? videoSrc : undefined}
                            poster={videoPoster}
                            className={`absolute inset-0 w-full h-full bg-transparent object-cover object-top transition-opacity duration-150 ${showVideo ? 'opacity-100' : 'opacity-0'}`}
                            muted
                            playsInline
                            preload={shouldLoad ? "metadata" : "none"}
                            onCanPlay={handleCanPlayThrough}
                            onLoadedData={handleCanPlayThrough}
                            onCanPlayThrough={handleCanPlayThrough}
                            onWaiting={handlePlaybackInterruption}
                            onStalled={handlePlaybackInterruption}
                            onPlaying={handlePlaying}
                            onEnded={handleEnded}
                            onPause={handlePause}
                            onError={handleError}
                            onProgress={handleProgress}
                        />
                    )}

                    {/* Fallback empty state when no poster and no video */}
                    {!videoPoster && !videoSrc && (
                        <div className="w-full h-full bg-transparent" />
                    )}
                </NextLink>
            </div>

            {/* Spacer */}
            <div className="h-[20px]"></div>

            {/* Info Block */}
            <NextLink href={`/product/${id}`} className="flex flex-col gap-[5px] px-2 w-full mx-auto items-center text-center">
                <Text size={11} weight="semibold" className="text-black tracking-wide leading-snug">{title}</Text>
            </NextLink>
            <div className="mt-[6px] flex w-full items-center justify-center gap-[10px] px-2">
                <CatalogQuantityControl
                    quantity={catalogQuantity}
                    onAdd={handleAddToCart}
                    onDecrease={handleDecreaseQuantity}
                    onIncrease={handleIncreaseQuantity}
                />
                <NextLink href={`/product/${id}`} className="flex flex-row items-center gap-[3px]">
                    <Text size={11} className="text-black leading-none">{price} ₽</Text>
                    {oldPrice && (
                        <Text size={11} className="text-[#A0A0A0] line-through leading-none">{oldPrice} ₽</Text>
                    )}
                </NextLink>
            </div>
        </div>
    );
};

