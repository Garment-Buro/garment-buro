"use client";

import { ProductCard } from '@/components/shared/ProductCard';
import { ProductTitle } from '@/components/shared/ProductTitle';
import type { CatalogSection } from '@/lib/catalog/types';
import type { CatalogProduct } from '@/lib/products/types';

type CatalogProductSlotProps = {
    product?: CatalogProduct;
    section: CatalogSection;
    index: number;
    priority: number;
    isEditing: boolean;
    onReplace: (section: CatalogSection, index: number) => void;
};

export const CatalogProductSlot = ({
    product,
    section,
    index,
    priority,
    isEditing,
    onReplace,
}: CatalogProductSlotProps) => {
    if (!product) {
        return (
            <div className="flex h-[358px] w-[200px] items-center justify-center bg-black/10 text-xs text-black/50">
                Empty Slot
            </div>
        );
    }

    return (
        <div className="group/slot relative z-[70]">
            <ProductCard
                id={product.id}
                title={<ProductTitle title={product.title} />}
                price={product.price}
                oldPrice={product.old_price}
                videoSrc={product.desktop_video || product.video_src}
                videoPoster={product.desktop_video_poster}
                priority={priority}
                cartTitle={product.title}
            />

            {isEditing && (
                <div className="absolute inset-0 z-50 flex cursor-pointer items-center justify-center bg-black/50 opacity-0 backdrop-blur-sm transition-opacity group-hover/slot:opacity-100">
                    <button
                        type="button"
                        className="rounded bg-white px-4 py-2 font-questrial text-sm uppercase text-black shadow-lg"
                        onClick={event => {
                            event.preventDefault();
                            onReplace(section, index);
                        }}
                    >
                        Заменить товар
                    </button>
                </div>
            )}
        </div>
    );
};
