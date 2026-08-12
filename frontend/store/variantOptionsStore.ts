import { create } from 'zustand';
import { getVariantOptions, updateVariantOptions } from '@/lib/api/options';
import type { ColorOption, VariantOptions } from '@/lib/options/types';
import {
    appendColorOption,
    appendSizeOption,
    DEFAULT_VARIANT_OPTIONS,
    normalizeVariantOptions,
} from '@/lib/options/utils/options';
import { runCatalogWrite } from '@/store/catalogWrite';

export type { ColorOption } from '@/lib/options/types';

interface VariantOptionsStore {
    colors: ColorOption[];
    sizes: string[];
    isLoaded: boolean;
    fetchOptions: () => Promise<void>;
    addColor: (label: string, hex: string) => Promise<void>;
    addSize: (size: string) => Promise<void>;
}

export const useVariantOptionsStore = create<VariantOptionsStore>((set, get) => ({
    ...DEFAULT_VARIANT_OPTIONS,
    isLoaded: false,

    fetchOptions: async () => {
        try {
            const options = normalizeVariantOptions(await getVariantOptions());
            set({ ...options, isLoaded: true });
        } catch (e) {
            console.error('Failed to fetch options', e);
            set({ isLoaded: true });
        }
    },

    addColor: async (label: string, hex: string) => {
        const { colors, sizes } = get();
        const previousOptions: VariantOptions = { colors, sizes };
        const nextOptions = appendColorOption(previousOptions, { label, hex });
        set(nextOptions);
        try {
            await runCatalogWrite(
                token => updateVariantOptions(nextOptions, token),
            );
        } catch (e) {
            console.error('Failed to save options', e);
        }
    },

    addSize: async (size: string) => {
        const { colors, sizes } = get();
        const previousOptions: VariantOptions = { colors, sizes };
        const nextOptions = appendSizeOption(previousOptions, size);
        set(nextOptions);
        try {
            await runCatalogWrite(
                token => updateVariantOptions(nextOptions, token),
            );
        } catch (e) {
            console.error('Failed to save options', e);
        }
    },
}));
