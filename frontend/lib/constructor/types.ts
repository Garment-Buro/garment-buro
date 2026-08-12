export type ModelView = "front" | "back";
export type GarmentDimensions = { widthCm: number; heightCm: number };
export type SleeveMode = "standard" | "height";
export type MeasurementRange = { min: number; max: number; defaultValue: number };
export type SizeFitRange = { length: MeasurementRange; width: MeasurementRange };

export type GarmentFit = {
    selectedSize: string;
    sleeveMode: SleeveMode;
    lengthCm: number;
    widthCm: number;
    lengthRange: { min: number; max: number };
    widthRange: { min: number; max: number };
};

export type CanvasBounds = { x: number; y: number; width: number; height: number };
export type UploadedImage = { src: string; width: number; height: number };
export type CanvasViewport = {
    stagePos: { x: number; y: number };
    stageScale: number;
    width: number;
    height: number;
};

export interface PlacedHardware {
    uid: string;
    variantId: string;
    x: number;
    y: number;
    scale: number;
    rotation?: number;
    baseLongSideCm?: number;
}

export type PlacedItemsByView = Record<ModelView, PlacedHardware[]>;

export type ConstructorDecoration = {
    view: ModelView;
    uid: string;
    variantId: string;
    name: string;
    price: number;
    image: string;
    widthCm: number;
    heightCm: number;
    x: number;
    y: number;
    scale: number;
    rotation: number;
};

export type ConstructorCustomization = {
    kind: "constructor";
    selectedSize: string;
    modelImages: Record<ModelView, string>;
    canvas: {
        widthCm: number;
        heightCm: number;
    };
    garment: {
        widthCm: number;
        heightCm: number;
    };
    fit?: GarmentFit;
    decorations: ConstructorDecoration[];
    totalPrice: number;
    comment?: string;
};

export type ConstructorDraftState = {
    activeView: ModelView;
    canvasPixelSize: {
        width: number;
        height: number;
    };
    modelBounds: CanvasBounds;
    customization: ConstructorCustomization;
};

export type ConstructorPageProps = {
    productId?: string | null;
    editCartItemId?: string | null;
    draftId?: string | null;
};

export type ClothingModel = {
    id: string;
    name: string;
    src: string;
    price: number;
};

export type HardwareCategory = "prints" | "rivets" | "distress" | "zippers" | "pullers" | "embroidery";

export type HardwareVariant = {
    id: string;
    categoryId: HardwareCategory;
    name: string;
    src: string;
    price: number;
    defaultWidth: number;
    defaultHeight?: number;
    minSizeMm?: number;
    maxSizeMm?: number;
    isCustom?: boolean;
    basePrice?: number;
};

export interface KonvaCanvasProps {
    selectedModel: ClothingModel | null;
    activeImageSrc?: string;
    modelBounds?: CanvasBounds;
    bottomInset?: number;
    placedItems: PlacedHardware[];
    hardwareMap: Record<string, HardwareVariant>;
    selectedHardwareUid: string | null;
    onSelectHardware: (uid: string | null) => void;
    onUpdateItem: (uid: string, newAttrs: Partial<PlacedHardware>) => void;
    onRemoveHardware?: (uid: string) => void;
    getHardwareScaleLimits?: (item: PlacedHardware, hardware: HardwareVariant) => { min: number; max: number };
    onCanvasInteraction?: () => void;
    onViewportChange?: (viewport: CanvasViewport) => void;
}
