"use client";

import { useEffect, useMemo } from 'react';
import {useConstructorPrice} from './useConstructorPrice';
import {constructorPriceRequest} from '@/lib/constructor/priceResource';

import { CUSTOM_UPLOAD_CATEGORIES, DECORATION_PAGE_SIZE } from '@/lib/constructor/constants';
import type {
    ClothingModel,
    ConstructorDraftState,
    GarmentFit,
    HardwareCategory,
    HardwareVariant,
    ModelView,
    PlacedHardware,
    PlacedItemsByView,
} from '@/lib/constructor/types';
import {
    chunkArray,
    getItemSizeCm,
    resolveConstructorGeometry,
    getProductImageList,
    versionConstructorMedia,
} from '@/lib/constructor/utils/constructor';
import type { ConstructorProduct } from '@/lib/constructor/product';
import { constructorVariantImages } from '@/lib/constructor/selection';

type ConstructorDerivedStateOptions = {
    product: ConstructorProduct | null;
    selectedSize: string;
    selectedColor: string | null;
    modelView: ModelView;
    selectedCategory: HardwareCategory;
    customDecorations: HardwareVariant[];
    placedItemsByView: PlacedItemsByView;
    selectedItemUid: string | null;
    restoredModelImages?: Record<ModelView, string> | null;
    restoredDraft?: ConstructorDraftState | null;
    selectedFit?: GarmentFit | null;
};

export const useConstructorDerivedState = ({
    product,
    selectedSize,
    selectedColor,
    modelView,
    selectedCategory,
    customDecorations,
    placedItemsByView,
    selectedItemUid,
    restoredModelImages,
    restoredDraft,
    selectedFit = null,
}: ConstructorDerivedStateOptions) => {
    const productImages = useMemo(() => {
        const variantImages = constructorVariantImages(product, { size: selectedSize, color: selectedColor });
        return variantImages.length ? variantImages : getProductImageList(product);
    }, [product, selectedSize, selectedColor]);
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
    const geometry = useMemo(() => resolveConstructorGeometry(product, selectedSize, restoredDraft, selectedFit, selectedColor), [product, selectedSize, restoredDraft, selectedFit, selectedColor]);
    const garmentDimensions = geometry.garment;
    const modelBounds = geometry.modelBounds;
    const canUploadCustomDecoration = CUSTOM_UPLOAD_CATEGORIES.includes(selectedCategory);
    const selectedModel = useMemo<ClothingModel | null>(() => {
        if (!product) return null;

        return {
            id: `product_${product.id}`,
            name: product.title,
            src: displayActiveImageSrc || versionConstructorMedia(getProductImageList(product)[0]) || '',
            price: product.price,
        };
    }, [displayActiveImageSrc, product]);
    const visibleCustomDecorations = useMemo(
        () => customDecorations.filter((decoration) => decoration.categoryId === selectedCategory),
        [customDecorations, selectedCategory],
    );
    const currentVariants = useMemo(
        () => visibleCustomDecorations,
        [visibleCustomDecorations],
    );
    const hardwareMap = useMemo(() => {
        const map: Record<string, HardwareVariant> = {};
        customDecorations.forEach((hardware) => {
            map[hardware.id] = hardware;
        });
        return map;
    }, [customDecorations]);
    const pricing = useConstructorPrice(constructorPriceRequest(product?.id ?? null, placedItemsByView));
    const decorationPrices = useMemo(() => Object.fromEntries(pricing.quote?.decorations.map(d => [d.uid, d.price]) || []), [pricing.quote]);
    const customizationPrice = pricing.quote?.customizationPrice ?? 0;
    const totalPrice = pricing.quote?.totalPrice ?? 0;
    const placedItemDetails = useMemo(() => (
        (Object.entries(placedItemsByView) as Array<[ModelView, PlacedHardware[]]>).flatMap(([view, items]) => (
            items.map((item) => {
                const hardware = hardwareMap[item.variantId];
                const size = hardware ? getItemSizeCm(item, hardware, geometry.pixelsPerCm) : { widthCm: 0, heightCm: 0 };

                return {
                    view,
                    item,
                    hardware,
                    widthCm: size.widthCm,
                    heightCm: size.heightCm,
                    price: decorationPrices[item.uid] ?? 0,
                };
            })
        ))
    ), [hardwareMap, placedItemsByView, geometry.pixelsPerCm, decorationPrices]);
    const decorationPages = useMemo(() => {
        if (!canUploadCustomDecoration) return chunkArray(currentVariants, DECORATION_PAGE_SIZE);

        const firstPageSize = DECORATION_PAGE_SIZE - 1;
        return [
            currentVariants.slice(0, firstPageSize),
            ...chunkArray(currentVariants.slice(firstPageSize), DECORATION_PAGE_SIZE),
        ];
    }, [canUploadCustomDecoration, currentVariants]);
    const getDecorationPanelPrice = (variant: HardwareVariant) => {
        const placedCustomItems = Object.values(placedItemsByView).flat().filter((item) => item.variantId === variant.id);
        const selectedPlacedItem = selectedItemUid
            ? placedCustomItems.find((item) => item.uid === selectedItemUid)
            : null;
        const priceSource = selectedPlacedItem || placedCustomItems[0];
        if (!pricing.quote) return '…';
        const price = priceSource ? decorationPrices[priceSource.uid] : pricing.quote.decorationBasePrice;
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
        geometry,
        canUploadCustomDecoration,
        selectedModel,
        currentVariants,
        hardwareMap,
        customizationPrice,
        totalPrice,
        pricing,
        decorationPrices,
        placedItemDetails,
        decorationPages,
        getDecorationPanelPrice,
    };
};
