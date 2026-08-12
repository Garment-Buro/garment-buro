"use client";

import { CartActionBar } from '@/components/cart/CartActionBar';
import { CatalogHintPopup } from '@/components/shared/ConstructorFlowPopup';
import { useCatalogPage } from '@/hooks/catalog/useCatalogPage';
import type { CatalogProduct } from '@/lib/products/types';
import type { LandingSettings } from '@/lib/settings/types';

import { CatalogDesktopLayout } from './CatalogDesktopLayout';
import { CatalogMobileLayout } from './CatalogMobileLayout';

type CatalogScreenProps = {
    isEditing?: boolean;
    initialProducts?: CatalogProduct[];
    initialSettings?: LandingSettings | null;
};

export const CatalogScreen = ({
    isEditing = false,
    initialProducts = [],
    initialSettings = null,
}: CatalogScreenProps) => {
    const catalog = useCatalogPage({ initialProducts, initialSettings });

    return (
        <div className="relative w-full">
            <CatalogHintPopup
                isOpen={catalog.isConstructorHintOpen}
                onBack={catalog.goBack}
                onContinue={catalog.closeConstructorHint}
            />

            {!catalog.settings || !catalog.sections ? (
                <div className="min-h-[100dvh] w-full bg-[#F2F2F2]" />
            ) : (
                <>
                    {isEditing && (
                        <div className="fixed top-[150px] right-[20px] z-[999] animate-pulse rounded border border-black/10 bg-white px-4 py-2 font-questrial text-sm text-black shadow-2xl">
                            Режим редактора. Наведите на товары или логотип (слева сверху) для редактирования.
                        </div>
                    )}
                    <CatalogDesktopLayout
                        {...catalog.sections}
                        isEditing={isEditing}
                        onReplace={catalog.replaceProductSlot}
                    />
                    <CatalogMobileLayout products={catalog.orderedProducts} />
                    <CartActionBar
                        visible={catalog.hasCartItems}
                        title={catalog.landingCartItem?.title || 'Корзина'}
                        color={catalog.landingCartItem?.color || ''}
                        price={catalog.landingCartItem?.price || 0}
                        cartItemId={catalog.landingCartItem?.id}
                        onAdd={catalog.goToCheckout}
                        onEdit={catalog.editCartItem}
                        onBuy={catalog.goToCheckout}
                    />
                </>
            )}
        </div>
    );
};
