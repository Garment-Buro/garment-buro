import type { CatalogSection } from '@/lib/catalog/types';
import type { CatalogProduct } from '@/lib/products/types';

import { CatalogProductSlot } from './CatalogProductSlot';

type CatalogProductSlotsProps = {
    products: CatalogProduct[];
    section: CatalogSection;
    startIndex: number;
    count: number;
    priorityStart: number;
    isEditing: boolean;
    onReplace: (section: CatalogSection, index: number) => void;
};

export const CatalogProductSlots = ({
    products,
    section,
    startIndex,
    count,
    priorityStart,
    isEditing,
    onReplace,
}: CatalogProductSlotsProps) => (
    <>
        {Array.from({ length: count }, (_, offset) => {
            const index = startIndex + offset;
            return (
                <CatalogProductSlot
                    key={`${section}-${index}`}
                    product={products[index]}
                    section={section}
                    index={index}
                    priority={priorityStart + offset}
                    isEditing={isEditing}
                    onReplace={onReplace}
                />
            );
        })}
    </>
);
