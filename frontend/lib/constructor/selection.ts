import type { CartItem } from '../cart/types.ts';
import { constructorImageUrls, type ConstructorProduct } from './product.ts';
import type { ConstructorCustomization, ModelView } from './types.ts';

export type ConstructorSelection = { size: string; color: string | null };
type Variant = NonNullable<ConstructorProduct['variants']>[number];
const stock = (value: number | undefined) => typeof value === 'number' && Number.isFinite(value) && value > 0 ? Math.floor(value) : 0;
const sizes = (product: ConstructorProduct) => [...new Set((product.sizes ?? []).map(x => x.trim()).filter(Boolean))];
const sizeOf = (variant: Variant) => variant.size ?? '';
const colorOf = (variant: Variant) => variant.color ?? '';

export function constructorVariant(product: ConstructorProduct | null, selection: ConstructorSelection): Variant | null {
    const matches = product?.variants?.filter(v => sizeOf(v) === selection.size && colorOf(v) === selection.color) || [];
    return matches.length === 1 ? matches[0] : null;
}

export function constructorVariantImages(product: ConstructorProduct | null, selection: ConstructorSelection): string[] {
    const variant = constructorVariant(product, selection);
    const images = constructorImageUrls(product, variant?.images, 'images');
    return images.length ? images : constructorImageUrls(product, variant?.images, 'preview_image').slice(0, 1);
}

export function constructorSelectionStock(product: ConstructorProduct | null, selection: ConstructorSelection): number {
    if (!product || selection.color === null) return 0;
    if (product.variants?.length) return stock(constructorVariant(product, selection)?.stock_quantity);
    const declared = sizes(product);
    return selection.color === '' && (declared.length ? declared.includes(selection.size) : selection.size === '')
        ? stock(product.stock_quantity) : 0;
}

export function constructorColorOptions(product: ConstructorProduct | null, size: string) {
    const variants = product?.variants?.filter(v => sizeOf(v) === size) || [];
    return [...new Set(variants.map(colorOf))].map(color => ({
        color,
        stock: constructorSelectionStock(product, { size, color }),
    }));
}

export function constructorSizeOptions(product: ConstructorProduct | null) {
    if (!product) return [];
    if (product.variants?.length) return [...new Set(product.variants.map(sizeOf))].map(size => ({
        size, stock: constructorColorOptions(product, size).reduce((sum, color) => sum + color.stock, 0),
    }));
    const declared = sizes(product);
    return (declared.length ? declared : ['']).map(size => ({ size, stock: stock(product.stock_quantity) }));
}

export function initialConstructorSelection(product: ConstructorProduct | null): ConstructorSelection {
    const options = constructorSizeOptions(product);
    const size = (options.find(x => x.stock > 0) || options[0])?.size ?? '';
    return selectConstructorSize(product, size, null);
}

/** Explicit size changes may choose the first available color; restoration never guesses it. */
export function selectConstructorSize(product: ConstructorProduct | null, size: string, preferredColor: string | null): ConstructorSelection {
    if (!product?.variants?.length) return { size, color: '' };
    const colors = constructorColorOptions(product, size);
    const preferred = colors.find(x => x.color === preferredColor && x.stock > 0);
    return { size, color: (preferred || colors.find(x => x.stock > 0) || colors[0])?.color ?? null };
}

export function restoreConstructorSelection(product: ConstructorProduct | null, size: string, color?: string | null): ConstructorSelection {
    if (color != null) return { size, color };
    if (!product?.variants?.length) return { size, color: '' };
    const colors = constructorColorOptions(product, size);
    return { size, color: colors.length === 1 ? colors[0].color : null };
}

export function constructorCartPayload(product: ConstructorProduct, selection: ConstructorSelection,
    customization: ConstructorCustomization, view: ModelView): Omit<CartItem, 'id'> | null {
    if (!constructorSelectionStock(product, selection)) return null;
    return {
        product_id: product.id, title: product.title, price: customization.totalPrice,
        image: customization.modelImages[view], size: selection.size, color: selection.color!, quantity: 1,
        customization: { ...customization, selectedSize: selection.size, selectedColor: selection.color! },
    };
}
