import type { CartItem } from '../../cart/types.ts';
import type { CatalogProduct } from '../../products/types.ts';
import type { LandingSettings } from '../../settings/types.ts';
import type { CatalogSection } from '../types.ts';

const SETTINGS_KEY_BY_SECTION: Record<CatalogSection, keyof Pick<
    LandingSettings,
    'hero_products' | 'showroom1_products' | 'showroom2_products'
>> = {
    hero: 'hero_products',
    showroom1: 'showroom1_products',
    showroom2: 'showroom2_products',
};

export const splitProductTitle = (title: string) => {
    const quoteIndex = title.indexOf('"');
    return quoteIndex === -1
        ? [title]
        : [title.substring(0, quoteIndex), title.substring(quoteIndex)];
};

export const parseCatalogMediaList = (value?: string) => value
    ? value.split(',').map(item => item.trim()).filter(Boolean)
    : [];

export const selectCatalogProducts = (products: CatalogProduct[], productIds: number[]) => (
    productIds
        .map(id => products.find(product => product.id === id) || products[id - 1] || products[0])
        .filter((product): product is CatalogProduct => Boolean(product))
);

export const getOrderedCatalogProducts = (
    products: CatalogProduct[],
    sections: CatalogProduct[][],
) => {
    const orderedProducts: CatalogProduct[] = [];
    const addedIds = new Set<number>();

    [...sections.flat(), ...products].forEach(product => {
        if (addedIds.has(product.id)) return;
        orderedProducts.push(product);
        addedIds.add(product.id);
    });

    return orderedProducts;
};

export const createCatalogSectionUpdate = (
    settings: LandingSettings,
    section: CatalogSection,
    index: number,
    productId: number,
): Partial<LandingSettings> => {
    const settingsKey = SETTINGS_KEY_BY_SECTION[section];
    const productIds = [...settings[settingsKey]];
    productIds[index] = productId;
    return { [settingsKey]: productIds };
};

export const getActiveCatalogCartItem = (
    items: CartItem[],
    activeItemId: string | null,
) => (activeItemId ? items.find(item => item.id === activeItemId) : undefined) || items[items.length - 1];
