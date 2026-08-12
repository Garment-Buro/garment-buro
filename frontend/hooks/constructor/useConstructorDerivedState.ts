"use client";

import { useEffect, useMemo } from 'react';

import { DEFAULT_DECORATION_CATALOG } from '@/lib/constructor/config/defaultDecorations';
import { CUSTOM_UPLOAD_CATEGORIES, DECORATION_PAGE_SIZE } from '@/lib/constructor/constants';
import type {
    ClothingModel,
    HardwareCategory,
    HardwareVariant,
    ModelView,
    PlacedHardware,
    PlacedItemsByView,
} from '@/lib/constructor/types';
import {
    chunkArray,
    formatDecorationPrice,
    getItemSizeCm,
    getModelBounds,
    getPlacedItemPrice,
    getProductDimensions,
    getProductImageList,
    versionConstructorMedia,
} from '@/lib/constructor/utils/constructor';
import type { ProductData } from '@/lib/products/types';

type ConstructorDerivedStateOptions = {
    product: ProductData | null;
    selectedSize: string;
    modelView: ModelView;
    selectedCategory: HardwareCategory;
    customDecorations: HardwareVariant[];
    placedItemsByView: PlacedItemsByView;
    selectedItemUid: string | null;
    restoredModelImages?: Record<ModelView, string> | null;
};

export const useConstructorDerivedState = ({
    product,
    selectedSize,
    modelView,
    selectedCategory,
    customDecorations,
    placedItemsByView,
    selectedItemUid,
    restoredModelImages,
}: ConstructorDerivedStateOptions) => {
    const productImages = useMemo(() => getProductImageList(product), [product]);
    const frontImage = restoredModelImages?.front || productImages[0] || null;
    const backImage = restoredModelImages?.back || productImages[1] || frontImage;
    const activeImageSrc = modelView === 'front' ? frontImage : backImage;
    const displayActiveImageSrc = useMemo(() => versionConstructorMedia(activeImageSrc), [activeImageSrc]);

    useEffect(() => {
        [frontImage, backImage].filter(Boolean).forEach((src) => {
            const versionedSrc = versionConstructorMedia(src);
            if (!versionedSrc) return;

            const preloadImage = new window.Image();
            preloadImage.src = versionedSrc;
        });
    }, [frontImage, backImage]);

    const placedItems = placedItemsByView[modelView];
    const garmentDimensions = useMemo(() => getProductDimensions(product, selectedSize), [product, selectedSize]);
    const modelBounds = useMemo(() => getModelBounds(garmentDimensions), [garmentDimensions]);
    const canUploadCustomDecoration = CUSTOM_UPLOAD_CATEGORIES.includes(selectedCategory);
    const selectedModel = useMemo<ClothingModel | null>(() => {
        if (!product) return null;

        return {
            id: `product_${product.id}`,
            name: product.title,
            src: displayActiveImageSrc || versionConstructorMedia(product.mobile_card_image) || versionConstructorMedia(product.image_left) || '',
            price: product.price,
        };
    }, [displayActiveImageSrc, product]);
    const visibleCustomDecorations = useMemo(
        () => customDecorations.filter((decoration) => decoration.categoryId === selectedCategory),
        [customDecorations, selectedCategory],
    );
    const currentVariants = useMemo(
        () => [
            ...visibleCustomDecorations,
            ...DEFAULT_DECORATION_CATALOG.filter((hardware) => hardware.categoryId === selectedCategory),
        ],
        [selectedCategory, visibleCustomDecorations],
    );
    const hardwareMap = useMemo(() => {
        const map: Record<string, HardwareVariant> = {};
        [...DEFAULT_DECORATION_CATALOG, ...customDecorations].forEach((hardware) => {
            map[hardware.id] = hardware;
        });
        return map;
    }, [customDecorations]);
    const customizationPrice = useMemo(() => (
        Object.values(placedItemsByView).flat().reduce((total, item) => (
            total + getPlacedItemPrice(item, hardwareMap[item.variantId])
        ), 0)
    ), [hardwareMap, placedItemsByView]);
    const totalPrice = (selectedModel?.price || 0) + customizationPrice;
    const placedItemDetails = useMemo(() => (
        (Object.entries(placedItemsByView) as Array<[ModelView, PlacedHardware[]]>).flatMap(([view, items]) => (
            items.map((item) => {
                const hardware = hardwareMap[item.variantId];
                const size = hardware ? getItemSizeCm(item, hardware) : { widthCm: 0, heightCm: 0 };

                return {
                    view,
                    item,
                    hardware,
                    widthCm: size.widthCm,
                    heightCm: size.heightCm,
                    price: getPlacedItemPrice(item, hardware),
                };
            })
        ))
    ), [hardwareMap, placedItemsByView]);
    const decorationPages = useMemo(() => {
        if (!canUploadCustomDecoration) return chunkArray(currentVariants, DECORATION_PAGE_SIZE);

        const firstPageSize = DECORATION_PAGE_SIZE - 1;
        return [
            currentVariants.slice(0, firstPageSize),
            ...chunkArray(currentVariants.slice(firstPageSize), DECORATION_PAGE_SIZE),
        ];
    }, [canUploadCustomDecoration, currentVariants]);
    const getDecorationPanelPrice = (variant: HardwareVariant) => {
        if (!variant.isCustom) return formatDecorationPrice(variant);

        const placedCustomItems = Object.values(placedItemsByView).flat().filter((item) => item.variantId === variant.id);
        const selectedPlacedItem = selectedItemUid
            ? placedCustomItems.find((item) => item.uid === selectedItemUid)
            : null;
        const priceSource = selectedPlacedItem || placedCustomItems[0];
        const price = priceSource ? getPlacedItemPrice(priceSource, variant) : variant.price;
        return `${price.toLocaleString('ru-RU')} ₽`;
    };

    return {
        frontImage,
        backImage,
        activeImageSrc,
        displayActiveImageSrc,
        placedItems,
        garmentDimensions,
        modelBounds,
        canUploadCustomDecoration,
        selectedModel,
        currentVariants,
        hardwareMap,
        customizationPrice,
        totalPrice,
        placedItemDetails,
        decorationPages,
        getDecorationPanelPrice,
    };
};
