import type { CatalogSection } from '@/lib/catalog/types';
import type { CatalogProduct } from '@/lib/products/types';

import { CatalogDesktopSection } from './CatalogDesktopSection';
import { CatalogProductSlots } from './CatalogProductSlots';

type CatalogDesktopLayoutProps = {
    heroProducts: CatalogProduct[];
    showroom1: CatalogProduct[];
    showroom2: CatalogProduct[];
    isEditing: boolean;
    onReplace: (section: CatalogSection, index: number) => void;
};

export const CatalogDesktopLayout = ({
    heroProducts,
    showroom1,
    showroom2,
    isEditing,
    onReplace,
}: CatalogDesktopLayoutProps) => {
    return (
        <div className="hidden w-full transition-opacity duration-300 md:block">
            <CatalogDesktopSection
                background="/landing_1.webp"
                backgroundAlt="Showroom Hero"
                variant="hero"
                left={<CatalogProductSlots products={heroProducts} section="hero" startIndex={0} count={2} priorityStart={1} isEditing={isEditing} onReplace={onReplace} />}
                right={<CatalogProductSlots products={heroProducts} section="hero" startIndex={2} count={2} priorityStart={3} isEditing={isEditing} onReplace={onReplace} />}
            />
            <CatalogDesktopSection
                background="/landing_2.webp"
                backgroundAlt="Showroom Section 1"
                variant="center"
                left={<CatalogProductSlots products={showroom1} section="showroom1" startIndex={0} count={3} priorityStart={5} isEditing={isEditing} onReplace={onReplace} />}
            />
            <CatalogDesktopSection
                background="/landing_3.webp"
                backgroundAlt="Showroom Section 2"
                variant="split"
                left={<CatalogProductSlots products={showroom2} section="showroom2" startIndex={0} count={2} priorityStart={8} isEditing={isEditing} onReplace={onReplace} />}
                right={<CatalogProductSlots products={showroom2} section="showroom2" startIndex={2} count={2} priorityStart={10} isEditing={isEditing} onReplace={onReplace} />}
            />
        </div>
    );
};
