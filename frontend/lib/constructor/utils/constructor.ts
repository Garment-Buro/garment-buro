import type { ProductData } from "../../products/types.ts";
import type { CartItem } from "../../cart/types.ts";
import { isSupportedImageFile } from "../../media/utils/upload.ts";

import {
    CANVAS_SIZE,
    CANVAS_REAL_SIZE_CM,
    CONSTRUCTOR_MEDIA_VERSION,
    CUSTOM_BASE_PRICE,
    DEFAULT_GARMENT_DIMENSIONS,
    DEFAULT_SIZE_DIMENSIONS,
    DEFAULT_SIZES,
    PX_PER_CM,
    SIZE_FIT_RANGES,
} from "../constants.ts";
import { DEFAULT_DECORATION_CATALOG } from "../config/defaultDecorations.ts";
import type {
    ConstructorCustomization,
    CanvasBounds,
    ClothingModel,
    GarmentDimensions,
    GarmentFit,
    MeasurementRange,
    ModelView,
    PlacedHardware,
    PlacedItemsByView,
    SizeFitRange,
    UploadedImage,
    HardwareVariant,
} from "../types.ts";
import { getCustomDecorationScaleLimits } from "./interaction.ts";

export const parseCsv = (value?: string) => {
    if (!value) return [];
    return value.split(",").map((item) => item.trim()).filter(Boolean);
};

export const versionConstructorMedia = (src: string | null | undefined) => {
    if (!src || !src.startsWith("/uploads/")) return src || null;
    const separator = src.includes("?") ? "&" : "?";
    return `${src}${separator}v=${CONSTRUCTOR_MEDIA_VERSION}`;
};

export const unique = (items: string[]) => Array.from(new Set(items.filter(Boolean)));

export const readUploadedImage = (file: File) => new Promise<UploadedImage>((resolve, reject) => {
    if (!isSupportedImageFile(file)) {
        reject(new Error("Поддерживаются только безопасные растровые изображения."));
        return;
    }
    const reader = new FileReader();
    reader.onload = () => {
        const src = String(reader.result || "");
        const image = new Image();
        image.onload = () => resolve({ src, width: image.naturalWidth || 1, height: image.naturalHeight || 1 });
        image.onerror = () => reject(new Error("Uploaded image could not be loaded"));
        image.src = src;
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
});

export const chunkArray = <T,>(items: T[], size: number) => {
    const chunks: T[][] = [];
    for (let index = 0; index < items.length; index += size) chunks.push(items.slice(index, index + size));
    return chunks;
};

export const clampCanvasPoint = (value: number) => Math.min(Math.max(value, 0), CANVAS_SIZE);

export const getDefaultDimensionsForSize = (size: string): GarmentDimensions => (
    DEFAULT_SIZE_DIMENSIONS[size] || DEFAULT_GARMENT_DIMENSIONS
);

export const getProductDimensions = (product: ProductData | null, selectedSize: string): GarmentDimensions => {
    const variantForSize = product?.variants?.find((variant) => variant.size === selectedSize);
    const variantWidth = Number(variantForSize?.width_cm || 0);
    const variantHeight = Number(variantForSize?.height_cm || 0);
    const defaultDimensions = getDefaultDimensionsForSize(selectedSize);

    return {
        widthCm: variantWidth || defaultDimensions.widthCm,
        heightCm: variantHeight || defaultDimensions.heightCm,
    };
};

export const clampMeasurement = (value: number, range: MeasurementRange) => (
    Math.min(Math.max(Math.round(value), range.min), range.max)
);

export const getFitRangeForSize = (size: string): SizeFitRange => SIZE_FIT_RANGES[size] || SIZE_FIT_RANGES.M;

export const createDefaultFit = (size: string, dimensions?: GarmentDimensions): GarmentFit => {
    const safeSize = size || "M";
    const range = getFitRangeForSize(safeSize);
    const lengthSource = dimensions?.heightCm && dimensions.heightCm >= range.length.min
        ? dimensions.heightCm
        : range.length.defaultValue;
    const widthSource = dimensions?.widthCm && dimensions.widthCm >= range.width.min
        ? dimensions.widthCm
        : range.width.defaultValue;

    return {
        selectedSize: safeSize,
        sleeveMode: "standard",
        lengthCm: clampMeasurement(lengthSource, range.length),
        widthCm: clampMeasurement(widthSource, range.width),
        lengthRange: { min: range.length.min, max: range.length.max },
        widthRange: { min: range.width.min, max: range.width.max },
    };
};

export const getModelBounds = (dimensions: GarmentDimensions): CanvasBounds => {
    const width = Math.min(CANVAS_SIZE, Math.max(1, dimensions.widthCm * PX_PER_CM));
    const height = Math.min(CANVAS_SIZE, Math.max(1, dimensions.heightCm * PX_PER_CM));
    return { x: (CANVAS_SIZE - width) / 2, y: (CANVAS_SIZE - height) / 2, width, height };
};

export const getHardwareSizePx = (hardware: HardwareVariant) => ({
    width: hardware.defaultWidth || 50,
    height: hardware.defaultHeight || hardware.defaultWidth || 50,
});

export const getItemSizeCm = (item: PlacedHardware, hardware: HardwareVariant) => {
    const sizePx = getHardwareSizePx(hardware);
    const widthCm = sizePx.width * (item.scale || 1) / PX_PER_CM;
    const heightCm = sizePx.height * (item.scale || 1) / PX_PER_CM;
    return { widthCm, heightCm, longSideCm: Math.max(widthCm, heightCm) };
};

export const getPlacedItemPrice = (item: PlacedHardware, hardware: HardwareVariant | undefined) => {
    if (!hardware) return 0;
    if (!hardware.isCustom) return hardware.price;
    const baseLongSideCm = item.baseLongSideCm || getItemSizeCm({ ...item, scale: 1 }, hardware).longSideCm || 1;
    const currentLongSideCm = getItemSizeCm(item, hardware).longSideCm;
    return Math.max(CUSTOM_BASE_PRICE, Math.round(CUSTOM_BASE_PRICE * (currentLongSideCm / baseLongSideCm)));
};

type BuildConstructorCustomizationOptions = {
    selectedModel: ClothingModel | null;
    selectedSize: string;
    selectedFit: GarmentFit | null;
    garmentDimensions: GarmentDimensions;
    placedItemsByView: PlacedItemsByView;
    hardwareMap: Record<string, HardwareVariant>;
    frontImage: string | null;
    backImage: string | null;
    totalPrice: number;
    comment: string;
};

export const buildConstructorCustomization = ({
    selectedModel,
    selectedSize,
    selectedFit,
    garmentDimensions,
    placedItemsByView,
    hardwareMap,
    frontImage,
    backImage,
    totalPrice,
    comment,
}: BuildConstructorCustomizationOptions): ConstructorCustomization | null => {
    if (!selectedModel) return null;
    const fit = selectedFit?.selectedSize === selectedSize
        ? selectedFit
        : createDefaultFit(selectedSize, garmentDimensions);
    const decorations = (Object.entries(placedItemsByView) as Array<[ModelView, PlacedHardware[]]>)
        .flatMap(([view, items]) => items.map((item) => {
            const hardware = hardwareMap[item.variantId];
            const size = hardware ? getItemSizeCm(item, hardware) : { widthCm: 0, heightCm: 0 };
            return {
                view,
                uid: item.uid,
                variantId: item.variantId,
                name: hardware?.name || "",
                price: getPlacedItemPrice(item, hardware),
                image: hardware?.src || "",
                widthCm: Math.round(size.widthCm),
                heightCm: Math.round(size.heightCm),
                x: item.x,
                y: item.y,
                scale: item.scale,
                rotation: item.rotation || 0,
                ...(hardware?.text ? {
                    text: hardware.text,
                    originalWidth: hardware.defaultWidth,
                    originalHeight: hardware.defaultHeight,
                } : {}),
            };
        }));

    return {
        kind: "constructor",
        selectedSize,
        modelImages: {
            front: frontImage || selectedModel.src,
            back: backImage || frontImage || selectedModel.src,
        },
        canvas: {
            widthCm: CANVAS_REAL_SIZE_CM,
            heightCm: CANVAS_REAL_SIZE_CM,
        },
        garment: {
            widthCm: fit.widthCm,
            heightCm: fit.lengthCm,
        },
        fit,
        decorations,
        totalPrice,
        comment,
    };
};

export const getHardwareScaleLimits = (item: PlacedHardware, hardware: HardwareVariant) => {
    const baseLongSideMm = Math.max(1, getItemSizeCm({ ...item, scale: 1 }, hardware).longSideCm * 10);
    const minScale = hardware.minSizeMm ? hardware.minSizeMm / baseLongSideMm : 0.25;
    const maxScale = hardware.maxSizeMm ? hardware.maxSizeMm / baseLongSideMm : 4;
    const safeMin = Math.max(0.01, Math.min(minScale, maxScale));
    const safeMax = Math.max(safeMin, maxScale);
    return getCustomDecorationScaleLimits({ isCustom: hardware.isCustom && !hardware.text, minScale: safeMin, maxScale: safeMax });
};

export const getPlacedItemsFromCustomization = (
    customization: ConstructorCustomization | undefined,
): PlacedItemsByView => {
    const decorations = customization?.decorations || [];
    const getItemsForView = (view: "front" | "back") => decorations
        .filter((decoration) => decoration.view === view)
        .map((decoration) => ({
            uid: decoration.uid,
            variantId: decoration.variantId,
            x: decoration.x,
            y: decoration.y,
            scale: decoration.scale,
            rotation: decoration.rotation,
            baseLongSideCm: Math.max(decoration.widthCm, decoration.heightCm) / Math.max(decoration.scale || 1, 0.01),
        }));
    return { front: getItemsForView("front"), back: getItemsForView("back") };
};

export const getPlacedItemsFromCartItem = (item: CartItem): PlacedItemsByView => (
    getPlacedItemsFromCustomization(item.customization)
);

export const getCustomDecorationsFromCustomization = (
    customization: ConstructorCustomization | undefined,
): HardwareVariant[] => {
    const knownHardwareIds = new Set(DEFAULT_DECORATION_CATALOG.map((hardware) => hardware.id));
    const customDecorations = customization?.decorations.filter((decoration) => (
        decoration.image && !knownHardwareIds.has(decoration.variantId)
    )) || [];
    const seenIds = new Set<string>();

    return customDecorations.flatMap((decoration): HardwareVariant[] => {
        if (seenIds.has(decoration.variantId)) return [];
        seenIds.add(decoration.variantId);
        const safeScale = Math.max(decoration.scale || 1, 0.01);
        const defaultWidth = decoration.originalWidth || Math.max(24, Math.round((decoration.widthCm / safeScale) * PX_PER_CM));
        const defaultHeight = decoration.originalHeight || Math.max(24, Math.round((decoration.heightCm / safeScale) * PX_PER_CM));
        const price = decoration.price || CUSTOM_BASE_PRICE;
        return [{
            id: decoration.variantId,
            categoryId: "prints",
            name: decoration.name || "свой принт",
            src: decoration.image,
            price,
            basePrice: price,
            defaultWidth,
            defaultHeight,
            minSizeMm: 10,
            maxSizeMm: decoration.text ? 600 : 300,
            isCustom: true,
            ...(decoration.text ? { text: decoration.text } : {}),
        }];
    });
};

export const getCustomDecorationsFromCartItem = (item: CartItem): HardwareVariant[] => (
    getCustomDecorationsFromCustomization(item.customization)
);

export const formatCm = (value: number) => `${Math.max(1, Math.round(value))} см`;
export const formatDecorationPrice = (variant: HardwareVariant) => variant.isCustom ? `${variant.price} ₽` : `+${variant.price} ₽`;

export const getProductImageList = (product: ProductData | null) => {
    if (!product) return [];
    const variantImages = product.variants?.find((variant) => parseCsv(variant.images).length > 0)?.images;
    const imageSets = [
        parseCsv(product.desktop_slider_images),
        parseCsv(variantImages),
        parseCsv(product.mobile_product_slider_images),
        parseCsv(product.mobile_slider_images),
        parseCsv(product.gallery_images),
        parseCsv(product.desktop_card_images),
        [product.image_left, product.image_right, product.mobile_card_image].filter(Boolean) as string[],
    ];
    return imageSets.find((images) => images.length > 0) || [];
};

export const getProductSizeOptions = (product: ProductData | null) => {
    const sizes = unique([...DEFAULT_SIZES, ...parseCsv(product?.sizes), ...(product?.variants?.map((variant) => variant.size) || [])]);
    return sizes.map((size) => {
        const variant = product?.variants?.find((item) => item.size === size);
        const defaultDimensions = getDefaultDimensionsForSize(size);
        return {
            size,
            stock: variant?.stock_quantity ?? 1,
            widthCm: variant?.width_cm || defaultDimensions.widthCm,
            heightCm: variant?.height_cm || defaultDimensions.heightCm,
        };
    });
};

export const getFirstAvailableSize = (product: ProductData | null) => {
    const variantSize = product?.variants?.find((variant) => variant.stock_quantity > 0)?.size;
    if (variantSize) return variantSize;
    const sizeOptions = getProductSizeOptions(product);
    return (sizeOptions.find((option) => option.stock > 0) || sizeOptions[0])?.size || "";
};
