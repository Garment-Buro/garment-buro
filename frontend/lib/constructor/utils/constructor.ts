import { constructorImageUrls, type ConstructorProduct } from "../product.ts";
import type { CartItem } from "../../cart/types.ts";

import {
    CANVAS_SIZE,
    CANVAS_REAL_SIZE_CM,
    CONSTRUCTOR_MEDIA_VERSION,
    DEFAULT_GARMENT_DIMENSIONS,
    DEFAULT_SIZE_DIMENSIONS,
    PX_PER_CM,
    SIZE_FIT_RANGES,
} from "../constants.ts";
import type {
    ConstructorCustomization,
    ConstructorDraftState,
    CanvasBounds,
    ClothingModel,
    GarmentDimensions,
    GarmentFit,
    MeasurementRange,
    ModelView,
    PlacedHardware,
    PlacedItemsByView,
    SizeFitRange,
    HardwareVariant,
} from "../types.ts";
import { getCustomDecorationScaleLimits } from "./interaction.ts";
import { constructorSizeOptions, initialConstructorSelection } from '../selection.ts';

export const versionConstructorMedia = (src: string | null | undefined) => {
    if (!src || !src.startsWith("/uploads/")) return src || null;
    const separator = src.includes("?") ? "&" : "?";
    return `${src}${separator}v=${CONSTRUCTOR_MEDIA_VERSION}`;
};

export const unique = (items: string[]) => Array.from(new Set(items.filter(Boolean)));

export { readUploadedImage } from '../imageInput.ts';

export const chunkArray = <T,>(items: T[], size: number) => {
    const chunks: T[][] = [];
    for (let index = 0; index < items.length; index += size) chunks.push(items.slice(index, index + size));
    return chunks;
};

export const clampCanvasPoint = (value: number, limit = CANVAS_SIZE) => Math.min(Math.max(value, 0), limit);

export const getDefaultDimensionsForSize = (size: string): GarmentDimensions => (
    DEFAULT_SIZE_DIMENSIONS[size] || DEFAULT_GARMENT_DIMENSIONS
);

export const getProductDimensions = (product: ConstructorProduct | null, selectedSize: string, selectedColor?: string | null): GarmentDimensions => {
    const variantForSize = product?.variants?.find((variant) => (variant.size ?? '') === selectedSize
        && (selectedColor === undefined || (variant.color ?? '') === selectedColor));
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
    const safeSize = size;
    const range = getFitRangeForSize(safeSize);
    const widthSource = dimensions?.widthCm && dimensions.widthCm >= range.width.min
        ? dimensions.widthCm
        : range.width.defaultValue;

    return {
        selectedSize: safeSize,
        sleeveMode: "standard",
        lengthCm: range.length.defaultValue,
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

export const resolveConstructorGeometry = (
    product: ConstructorProduct | null,
    selectedSize: string,
    restored: ConstructorDraftState | null = null,
    selectedFit: GarmentFit | null = null,
    selectedColor?: string | null,
) => {
    const canvasPixelSize = restored?.canvasPixelSize || { width: CANVAS_SIZE, height: CANVAS_SIZE };
    const canvas = restored?.customization.canvas || { widthCm: CANVAS_REAL_SIZE_CM, heightCm: CANVAS_REAL_SIZE_CM };
    const pixelsPerCm = { x: canvasPixelSize.width / canvas.widthCm, y: canvasPixelSize.height / canvas.heightCm };
    const savedFit = restored && (restored.customization.fit || createDefaultFit(restored.customization.selectedSize, restored.customization.garment));
    const fitUnchanged = !selectedFit || (savedFit?.selectedSize === selectedFit.selectedSize
        && savedFit.widthCm === selectedFit.widthCm);
    const sameSelection = restored?.customization.selectedSize === selectedSize
        && (selectedColor === undefined || restored.customization.selectedColor === selectedColor);
    const preserve = sameSelection && fitUnchanged;
    const catalogDimensions = getProductDimensions(product, selectedSize, selectedColor);
    const garment = preserve ? restored.customization.garment
        : selectedFit?.selectedSize === selectedSize ? { widthCm: selectedFit.widthCm,
            heightCm: sameSelection ? restored.customization.garment.heightCm : catalogDimensions.heightCm }
            : catalogDimensions;
    const width = Math.min(canvasPixelSize.width, Math.max(1, garment.widthCm * pixelsPerCm.x));
    const height = Math.min(canvasPixelSize.height, Math.max(1, garment.heightCm * pixelsPerCm.y));
    const modelBounds = preserve ? restored.modelBounds
        : { x: (canvasPixelSize.width - width) / 2, y: (canvasPixelSize.height - height) / 2, width, height };
    return { canvasPixelSize, canvas, garment, modelBounds, pixelsPerCm };
};
type ConstructorGeometry = ReturnType<typeof resolveConstructorGeometry>;
type PixelsPerCm = { x: number; y: number };
const defaultPixelsPerCm = { x: PX_PER_CM, y: PX_PER_CM };

export const getHardwareSizePx = (hardware: HardwareVariant) => ({
    width: hardware.defaultWidth || 50,
    height: hardware.defaultHeight || hardware.defaultWidth || 50,
});

export const getItemSizeCm = (item: PlacedHardware, hardware: HardwareVariant, pixelsPerCm: PixelsPerCm = defaultPixelsPerCm) => {
    const sizePx = getHardwareSizePx(hardware);
    const widthCm = sizePx.width * (item.scale || 1) / pixelsPerCm.x;
    const heightCm = sizePx.height * (item.scale || 1) / pixelsPerCm.y;
    return { widthCm, heightCm, longSideCm: Math.max(widthCm, heightCm) };
};

type BuildConstructorCustomizationOptions = {
    selectedModel: ClothingModel | null;
    selectedSize: string;
    selectedColor?: string;
    selectedFit: GarmentFit | null;
    garmentDimensions: GarmentDimensions;
    placedItemsByView: PlacedItemsByView;
    hardwareMap: Record<string, HardwareVariant>;
    frontImage: string | null;
    backImage: string | null;
    totalPrice: number;
    decorationPrices?: Record<string, number>;
    comment: string;
    geometry?: ConstructorGeometry;
};

export const buildConstructorCustomization = ({
    selectedModel,
    selectedSize,
    selectedColor,
    selectedFit,
    garmentDimensions,
    placedItemsByView,
    hardwareMap,
    frontImage,
    backImage,
    totalPrice,
    decorationPrices = {},
    comment,
    geometry,
}: BuildConstructorCustomizationOptions): ConstructorCustomization | null => {
    if (!selectedModel) return null;
    const fit = selectedFit?.selectedSize === selectedSize
        ? selectedFit
        : createDefaultFit(selectedSize, garmentDimensions);
    const decorations = (Object.entries(placedItemsByView) as Array<[ModelView, PlacedHardware[]]>)
        .flatMap(([view, items]) => items.map((item) => {
            const hardware = hardwareMap[item.variantId];
            const size = hardware ? getItemSizeCm(item, hardware, geometry?.pixelsPerCm) : { widthCm: 0, heightCm: 0 };
            return {
                view,
                uid: item.uid,
                variantId: item.variantId,
                ...(hardware?.categoryId ? { categoryId: hardware.categoryId } : {}),
                name: hardware?.name || "",
                price: decorationPrices[item.uid] ?? 0,
                image: hardware?.src || "",
                widthCm: size.widthCm,
                heightCm: size.heightCm,
                x: item.x,
                y: item.y,
                scale: item.scale,
                rotation: item.rotation || 0,
                ...(hardware ? {
                    originalWidth: hardware.defaultWidth,
                    originalHeight: hardware.defaultHeight || hardware.defaultWidth,
                } : {}),
                ...(hardware?.text ? { text: hardware.text } : {}),
            };
        }));

    return {
        kind: "constructor",
        selectedSize,
        ...(selectedColor !== undefined ? { selectedColor } : {}),
        modelImages: {
            front: frontImage || selectedModel.src,
            back: backImage || frontImage || selectedModel.src,
        },
        canvas: geometry?.canvas || {
            widthCm: CANVAS_REAL_SIZE_CM,
            heightCm: CANVAS_REAL_SIZE_CM,
        },
        garment: geometry?.garment || {
            widthCm: fit.widthCm,
            heightCm: garmentDimensions.heightCm,
        },
        fit,
        ...(geometry ? { geometry: { canvasPixelSize: geometry.canvasPixelSize, modelBounds: geometry.modelBounds } } : {}),
        decorations,
        totalPrice,
        comment,
    };
};

export const getHardwareScaleLimits = (item: PlacedHardware, hardware: HardwareVariant, pixelsPerCm: PixelsPerCm = defaultPixelsPerCm) => {
    const baseLongSideMm = Math.max(1, getItemSizeCm({ ...item, scale: 1 }, hardware, pixelsPerCm).longSideCm * 10);
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
        }));
    return { front: getItemsForView("front"), back: getItemsForView("back") };
};

export const getPlacedItemsFromCartItem = (item: CartItem): PlacedItemsByView => (
    getPlacedItemsFromCustomization(item.customization)
);

export const getConstructorDraftFromCartItem = (item: Pick<CartItem, 'customization' | 'image'>): ConstructorDraftState | null => {
    const customization = item.customization;
    if (!customization || customization.kind !== 'constructor') return null;
    const positive = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value > 0;
    if (![customization.canvas?.widthCm, customization.canvas?.heightCm,
        customization.garment?.widthCm, customization.garment?.heightCm].every(positive)) return null;
    const mapping = customization.geometry;
    const validMapping = mapping
        && [mapping.canvasPixelSize?.width, mapping.canvasPixelSize?.height, mapping.modelBounds?.width, mapping.modelBounds?.height]
            .every(value => positive(value) && value <= 16384)
        && [mapping.modelBounds?.x, mapping.modelBounds?.y].every(value => typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= 1_000_000);
    const canvasPixelSize = validMapping ? mapping.canvasPixelSize : { width: CANVAS_SIZE, height: CANVAS_SIZE };
    const width = Math.min(canvasPixelSize.width, customization.garment.widthCm * canvasPixelSize.width / customization.canvas.widthCm);
    const height = Math.min(canvasPixelSize.height, customization.garment.heightCm * canvasPixelSize.height / customization.canvas.heightCm);
    return {
        activeView: item.image === customization.modelImages.back && customization.modelImages.front !== customization.modelImages.back ? 'back' : 'front',
        canvasPixelSize,
        modelBounds: validMapping ? mapping.modelBounds : { x: (canvasPixelSize.width - width) / 2, y: (canvasPixelSize.height - height) / 2, width, height },
        customization,
    };
};

export const getCustomDecorationsFromCustomization = (
    customization: ConstructorCustomization | undefined,
    pixelsPerCm: PixelsPerCm = defaultPixelsPerCm,
): HardwareVariant[] => {
    const customDecorations = customization?.decorations.filter(decoration => decoration.image) || [];
    const seenIds = new Set<string>();

    return customDecorations.flatMap((decoration): HardwareVariant[] => {
        if (seenIds.has(decoration.variantId)) return [];
        seenIds.add(decoration.variantId);
        const safeScale = Math.max(decoration.scale || 1, 0.01);
        const defaultWidth = decoration.originalWidth || Math.max(1, (decoration.widthCm / safeScale) * pixelsPerCm.x);
        const defaultHeight = decoration.originalHeight || Math.max(1, (decoration.heightCm / safeScale) * pixelsPerCm.y);
        const price = decoration.price ?? 0;
        return [{
            id: decoration.variantId,
            categoryId: decoration.categoryId || "prints",
            name: decoration.name || "свой принт",
            src: decoration.image,
            price,
            defaultWidth,
            defaultHeight,
            minSizeMm: 10,
            maxSizeMm: decoration.text ? 600 : 300,
            isCustom: true,
            ...(decoration.text ? { text: decoration.text } : {}),
        }];
    });
};

export const formatCm = (value: number) => `${Math.max(1, Math.round(value))} см`;

export const getProductImageList = (product: ConstructorProduct | null) => {
    if (!product) return [];
    const role = (name: string) => constructorImageUrls(product, product.images, name);
    const variantImages = product.variants?.map(variant => constructorImageUrls(product, variant.images, 'images')).find(images => images.length > 0) ?? [];
    const imageSets = [
        role('desktop_slider_images'), variantImages,
        role('mobile_product_slider_images'), role('mobile_slider_images'),
        role('gallery_images'), role('desktop_card_images'),
        ['image_left', 'image_right', 'mobile_card_image'].flatMap(name => role(name).slice(0, 1)),
    ];
    return imageSets.find((images) => images.length > 0) || [];
};

export const getProductSizeOptions = (product: ConstructorProduct | null) => {
    return constructorSizeOptions(product).map(({ size, stock }) => {
        const variant = product?.variants?.find((item) => item.size === size);
        const defaultDimensions = getDefaultDimensionsForSize(size);
        return {
            size,
            stock,
            widthCm: variant?.width_cm || defaultDimensions.widthCm,
            heightCm: variant?.height_cm || defaultDimensions.heightCm,
        };
    });
};

export const getFirstAvailableSize = (product: ConstructorProduct | null) => {
    return initialConstructorSelection(product).size;
};
