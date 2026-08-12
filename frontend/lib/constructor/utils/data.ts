import type { HardwareCategory, HardwareVariant } from "../types.ts";

export const createRepeatedHardware = (
    categoryId: HardwareCategory,
    prefix: string,
    price: number,
    defaultWidth: number,
    count: number,
    defaultHeight?: number,
    minSizeMm = 10,
    maxSizeMm = 300,
) => Array.from({ length: count }, (_, index): HardwareVariant => {
    const imageIndex = (index % 7) + 1;
    return {
        id: `h_${categoryId}_${index + 1}`,
        categoryId,
        name: `${prefix} ${String(index + 1).padStart(2, "0")}`,
        src: `/mock/${categoryId}/${imageIndex}.webp`,
        price,
        defaultWidth,
        minSizeMm,
        maxSizeMm,
        ...(defaultHeight ? { defaultHeight } : {}),
    };
});
