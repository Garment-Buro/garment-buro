import type { CSSProperties } from "react";

import type { GarmentDimensions, HardwareCategory, SizeFitRange } from "./types.ts";

export const CONSTRUCTOR_OVERLAY_VIEWPORT_STYLE = {
    position: "fixed",
    inset: 0,
    width: "100%",
} satisfies CSSProperties;

export const CONSTRUCTOR_INSTRUCTION_OVERLAY_VIEWPORT_STYLE = {
    ...CONSTRUCTOR_OVERLAY_VIEWPORT_STYLE,
    paddingTop: "max(52px, calc(env(safe-area-inset-top) + 42px))",
} satisfies CSSProperties;

export const CANVAS_SIZE = 800;
export const CONSTRUCTOR_MIN_STAGE_SCALE = 0.35;
export const CONSTRUCTOR_MAX_STAGE_SCALE = 3;
export const DEFAULT_CONSTRUCTOR_MODEL_BOUNDS = {
    x: 0,
    y: 0,
    width: CANVAS_SIZE,
    height: CANVAS_SIZE,
};
export const CANVAS_REAL_SIZE_CM = 80;
export const PX_PER_CM = CANVAS_SIZE / CANVAS_REAL_SIZE_CM;
export const SIZE_MODAL_MODEL_HEIGHT_CM = 168;

export const DEFAULT_SIZE_DIMENSIONS: Record<string, GarmentDimensions> = {
    XS: { widthCm: 64, heightCm: 74 },
    S: { widthCm: 66, heightCm: 76 },
    M: { widthCm: 68, heightCm: 78 },
    L: { widthCm: 70, heightCm: 80 },
    XL: { widthCm: 72, heightCm: 80 },
    XXL: { widthCm: 76, heightCm: 82 },
};

export const SIZE_FIT_RANGES: Record<string, SizeFitRange> = {
    XS: {
        length: { min: 154, max: 178, defaultValue: 166 },
        width: { min: 64, max: 78, defaultValue: 70 },
    },
    S: {
        length: { min: 156, max: 182, defaultValue: 170 },
        width: { min: 70, max: 84, defaultValue: 76 },
    },
    M: {
        length: { min: 162, max: 188, defaultValue: 176 },
        width: { min: 72, max: 88, defaultValue: 80 },
    },
    L: {
        length: { min: 168, max: 194, defaultValue: 182 },
        width: { min: 76, max: 92, defaultValue: 84 },
    },
    XL: {
        length: { min: 174, max: 200, defaultValue: 188 },
        width: { min: 80, max: 98, defaultValue: 90 },
    },
    XXL: {
        length: { min: 178, max: 206, defaultValue: 194 },
        width: { min: 84, max: 104, defaultValue: 96 },
    },
};

export const DEFAULT_SIZES = Object.keys(DEFAULT_SIZE_DIMENSIONS);
export const DEFAULT_GARMENT_DIMENSIONS = DEFAULT_SIZE_DIMENSIONS.M;
export const CUSTOM_UPLOAD_CATEGORIES: HardwareCategory[] = ["prints"];
export const CUSTOM_BASE_PRICE = 80;
export const DECORATION_PAGE_SIZE = 10;
export const ROTATE_PANEL_GAP = 18;
export const ROTATE_CONTROLS_HEIGHT = 45;
export const COLLAPSED_PANEL_BASE_HEIGHT = 150;
export const CONSTRUCTOR_MEDIA_VERSION = "constructor-20260603";
