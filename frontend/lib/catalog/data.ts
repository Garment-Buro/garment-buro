import { getServerProducts } from '@/lib/api/products.server';
import { getServerLandingSettings } from '@/lib/api/settings.server';
import type { CatalogProduct } from '@/lib/products/types';
import type { LandingSettings } from '@/lib/settings/types';

export const getCatalogData = async (): Promise<{
    products: CatalogProduct[];
    settings: LandingSettings | null;
}> => {
    try {
        const [products, settings] = await Promise.all([
            getServerProducts(),
            getServerLandingSettings(),
        ]);
        return { products, settings };
    } catch {
        return { products: [], settings: null };
    }
};
