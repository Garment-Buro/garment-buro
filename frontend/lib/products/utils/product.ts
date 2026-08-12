import type { ProductData } from '../types.ts';

export const parseProductMediaList = (value?: string) => value
    ? value.split(',').map(item => item.trim()).filter(Boolean)
    : [];

const splitProductMediaList = (value?: string) => value
    ? value.split(',').filter(Boolean)
    : [];

export const normalizeProductDescription = (description: string) => description
    .replace(/\r\n?/g, '\n')
    .replace(/[\u2028\u2029]\n?/g, '\n');

export const getPreferredVariant = (product: ProductData) => (
    product.variants?.find(variant => variant.stock_quantity > 0) || product.variants?.[0]
);

export const getFallbackGalleryForProduct = (product: ProductData) => [
    ...parseProductMediaList(product.mobile_product_slider_images),
    ...parseProductMediaList(product.mobile_slider_images),
    ...parseProductMediaList(product.desktop_slider_images),
    ...parseProductMediaList(product.desktop_card_images),
    product.mobile_card_image,
    product.image_left,
    product.image_right,
].filter((image): image is string => Boolean(image));

export const getPenultimateProductImage = (product: ProductData) => {
    const images = getFallbackGalleryForProduct(product);
    if (images.length >= 2) return images[images.length - 2];
    return images[0] || '/landing-bg.webp';
};

export const getPrimaryProductImage = (product: ProductData) => (
    getFallbackGalleryForProduct(product)[0] || '/landing-bg.webp'
);

export const getProductCartImage = (product: ProductData) => (
    product.mobile_card_image || getPrimaryProductImage(product)
);

export const localizeProductColor = (color: string) => {
    if (color === 'black') return 'Черный';
    if (color === 'white') return 'Белый';
    return color;
};

export const getProductVariantPresentation = (
    product: ProductData | null,
    selectedColor: string,
    selectedSize: string,
) => {
    const colorMap = new Map<string, string>();
    product?.variants?.forEach(variant => {
        if (!colorMap.has(variant.color)) colorMap.set(variant.color, variant.color_hex || '#888888');
    });
    const colorOptions = Array.from(colorMap.entries()).map(([label, hex]) => ({ label, hex }));
    const sizesForSelectedColor = product?.variants
        ?.filter(variant => variant.color === selectedColor)
        .map(variant => ({ size: variant.size, stock: variant.stock_quantity })) || [];
    const currentVariant = product?.variants?.find(
        variant => variant.color === selectedColor && variant.size === selectedSize,
    );
    const currentStock = currentVariant?.stock_quantity ?? product?.stock_quantity ?? 0;
    const variantImages = splitProductMediaList(currentVariant?.images);
    const desktopSliderImages = variantImages.length > 0
        ? variantImages
        : splitProductMediaList(product?.desktop_slider_images || product?.gallery_images);
    const mobileProductSlider = product?.mobile_product_slider_images
        ? splitProductMediaList(product.mobile_product_slider_images)
        : null;
    const mobileSliderImages = variantImages.length > 0
        ? variantImages
        : mobileProductSlider ?? (product?.mobile_slider_images
            ? splitProductMediaList(product.mobile_slider_images)
            : desktopSliderImages);

    return {
        colorOptions,
        sizesForSelectedColor,
        currentVariant,
        currentStock,
        desktopSliderImages,
        mobileSliderImages,
    };
};

export const getReviewPreviewImages = (products: ProductData[], currentProductId?: number) => {
    if (!currentProductId || products.length === 0) return [];
    const otherProducts = products
        .filter(product => product.id !== currentProductId)
        .sort((first, second) => first.id - second.id);
    const startIndex = otherProducts.length > 0 ? currentProductId % otherProducts.length : 0;
    const rotatedProducts = [
        ...otherProducts.slice(startIndex),
        ...otherProducts.slice(0, startIndex),
    ];
    return rotatedProducts.slice(0, 6).map(getPenultimateProductImage);
};

export const getNextProducts = (products: ProductData[], currentProductId?: number) => {
    if (!currentProductId || products.length < 2) return [];
    const currentIndex = products.findIndex(product => product.id === currentProductId);
    if (currentIndex === -1) return [];

    const result: ProductData[] = [];
    const maxCount = Math.min(2, products.length - 1);
    for (let offset = 1; offset <= maxCount; offset += 1) {
        const nextProduct = products[(currentIndex + offset) % products.length];
        if (nextProduct && nextProduct.id !== currentProductId) result.push(nextProduct);
    }
    return result;
};

export const getRelatedProductPages = (products: ProductData[]) => {
    const pages: ProductData[][] = [];
    const relatedProducts = products.slice(0, 30);
    for (let index = 0; index < relatedProducts.length; index += 6) {
        pages.push(relatedProducts.slice(index, index + 6));
    }
    return pages.slice(0, 5);
};

export const fillReviewImages = (images: string[], targetCount = 6) => (
    images.length >= targetCount
        ? images.slice(0, targetCount)
        : [...images, ...Array.from({ length: targetCount - images.length }, () => '/landing-bg.webp')]
);
