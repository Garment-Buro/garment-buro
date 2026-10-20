import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ServiceFavoritesState {
    ids: string[];
    toggle: (id: string) => void;
}

// Preview catalog IDs stay separate from real cart/product IDs until catalog integration.
export const useServiceFavoritesStore = create<ServiceFavoritesState>()(persist(set => ({
    ids: [],
    toggle: id => set(state => ({
        ids: state.ids.includes(id) ? state.ids.filter(value => value !== id) : [...state.ids, id],
    })),
}), {
    name: 'garment-buro-service-preview-favorites',
    partialize: state => ({ ids: state.ids }),
}));
