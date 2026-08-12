import { create } from 'zustand';
import { getLandingSettings, updateLandingSettings } from '@/lib/api/settings';
import type { LandingSettings } from '@/lib/settings/types';
import { runCatalogWrite } from '@/store/catalogWrite';

export type { LandingSettings } from '@/lib/settings/types';

interface SettingsStore {
    settings: LandingSettings | null;
    isLoading: boolean;
    fetchSettings: () => Promise<void>;
    updateSettings: (newSettings: Partial<LandingSettings>) => Promise<void>;
}

export const useSettingsStore = create<SettingsStore>((set, get) => ({
    settings: null,
    isLoading: true,
    fetchSettings: async () => {
        try {
            const settings = await getLandingSettings();
            set({ settings, isLoading: false });
        } catch (error) {
            console.error("Failed to fetch settings:", error);
            set({ isLoading: false });
        }
    },
    updateSettings: async (newSettings: Partial<LandingSettings>) => {
        const currentSettings = get().settings;
        if (!currentSettings) return;

        const updated = { ...currentSettings, ...newSettings };

        // Optimistic update
        set({ settings: updated });

        try {
            await runCatalogWrite(
                token => updateLandingSettings(updated, token),
            );
        } catch (error) {
            console.error(error);
            // Revert on failure
            set({ settings: currentSettings });
        }
    }
}));
