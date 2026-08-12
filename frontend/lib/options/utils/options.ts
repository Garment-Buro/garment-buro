import type { ColorOption, VariantOptions } from '@/lib/options/types';

export const DEFAULT_VARIANT_OPTIONS: VariantOptions = {
    colors: [
        { label: 'Черный', hex: '#1A1A1A' },
        { label: 'Белый', hex: '#FFFFFF' },
    ],
    sizes: ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
};

export const normalizeVariantOptions = (
    options: Partial<VariantOptions> | null | undefined,
): VariantOptions => ({
    colors: Array.isArray(options?.colors) ? options.colors : [],
    sizes: Array.isArray(options?.sizes) ? options.sizes : [],
});

export const appendColorOption = (
    options: VariantOptions,
    color: ColorOption,
): VariantOptions => ({
    ...options,
    colors: [...options.colors, color],
});

export const appendSizeOption = (
    options: VariantOptions,
    size: string,
): VariantOptions => ({
    ...options,
    sizes: [...options.sizes, size],
});
