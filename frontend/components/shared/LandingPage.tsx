import { CatalogScreen } from '@/components/catalog/CatalogScreen';
import type { CatalogProduct } from '@/lib/products/types';
import type { LandingSettings } from '@/lib/settings/types';

export type LandingProduct = CatalogProduct;

type LandingPageProps = {
    isEditing?: boolean;
    initialProducts?: CatalogProduct[];
    initialSettings?: LandingSettings | null;
};

export const LandingPage = (props: LandingPageProps) => <CatalogScreen {...props} />;
