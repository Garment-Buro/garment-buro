import { normalizeMediaUrl, parseMediaCsv } from '../../media/utils/mediaUrl.ts';
import type {
    AdminProductFormResponse,
    AdminProductPayload,
    ProductVariantData,
} from '@/lib/products/types';

export type AdminProductFormValues = {
    title: string;
    price: string;
    oldPrice: string;
    description: string;
    weight: string;
    height: string;
    width: string;
    length: string;
    stockQuantity: string;
    desktopVideo: string;
    desktopVideoPoster: string;
    desktopCardImages: string[];
    desktopSliderImages: string[];
    mobileCardImage: string;
    mobileVideoPoster: string;
    mobileSliderImages: string[];
    mobileProductSliderImages: string[];
    mobileSizeChartFirst: string;
    sizeChartImg1: string;
    sizeChartImg2: string;
    variants: ProductVariantData[];
};

export const EMPTY_ADMIN_PRODUCT_FORM: AdminProductFormValues = {
    title: '', price: '', oldPrice: '', description: '', weight: '0', height: '0', width: '0', length: '0', stockQuantity: '0',
    desktopVideo: '', desktopVideoPoster: '', desktopCardImages: [], desktopSliderImages: [],
    mobileCardImage: '', mobileVideoPoster: '', mobileSliderImages: [], mobileProductSliderImages: [],
    mobileSizeChartFirst: '', sizeChartImg1: '', sizeChartImg2: '', variants: [],
};

export const createEmptyProductVariant = (): ProductVariantData => ({
    size: 'M', color: 'Черный', color_hex: '#1A1A1A', stock_quantity: 0,
    width_cm: null, height_cm: null, preview_image: '', images: '',
});

export const mapAdminProductToForm = (data: AdminProductFormResponse): AdminProductFormValues => ({
    title: data.title || '',
    price: data.price?.toString() || '',
    oldPrice: data.old_price?.toString() || '',
    description: data.description || '',
    weight: data.weight?.toString() || '0',
    height: data.height?.toString() || '0',
    width: data.width?.toString() || '0',
    length: data.length?.toString() || '0',
    stockQuantity: data.stock_quantity?.toString() || '0',
    desktopVideo: normalizeMediaUrl(data.desktop_video),
    desktopVideoPoster: normalizeMediaUrl(data.desktop_video_poster),
    desktopCardImages: parseMediaCsv(data.desktop_card_images),
    desktopSliderImages: parseMediaCsv(data.desktop_slider_images),
    mobileCardImage: normalizeMediaUrl(data.mobile_card_image),
    mobileVideoPoster: normalizeMediaUrl(data.mobile_video_poster),
    mobileSliderImages: parseMediaCsv(data.mobile_slider_images),
    mobileProductSliderImages: parseMediaCsv(data.mobile_product_slider_images),
    mobileSizeChartFirst: normalizeMediaUrl(data.mobile_size_chart_first),
    sizeChartImg1: normalizeMediaUrl(data.size_chart_img_1),
    sizeChartImg2: normalizeMediaUrl(data.size_chart_img_2),
    variants: data.variants?.map((variant) => ({
        id: variant.id,
        size: variant.size || '', color: variant.color || '', color_hex: variant.color_hex || '#000000',
        stock_quantity: variant.stock_quantity || 0,
        width_cm: variant.width_cm ?? null, height_cm: variant.height_cm ?? null,
        preview_image: normalizeMediaUrl(variant.preview_image),
        images: parseMediaCsv(variant.images).join(','),
    })) || [],
});

export const createAdminProductPayload = (form: AdminProductFormValues): AdminProductPayload => ({
    title: form.title,
    price: parseFloat(form.price),
    old_price: form.oldPrice ? parseFloat(form.oldPrice) : null,
    description: form.description || null,
    weight: parseFloat(form.weight), height: parseFloat(form.height), width: parseFloat(form.width), length: parseFloat(form.length),
    stock_quantity: parseInt(form.stockQuantity),
    desktop_video: form.desktopVideo || null,
    desktop_video_poster: form.desktopVideoPoster || null,
    desktop_card_images: form.desktopCardImages.length ? form.desktopCardImages.join(',') : null,
    desktop_slider_images: form.desktopSliderImages.length ? form.desktopSliderImages.join(',') : null,
    mobile_card_image: form.mobileCardImage || null,
    mobile_video_poster: form.mobileVideoPoster || null,
    mobile_slider_images: form.mobileSliderImages.length ? form.mobileSliderImages.join(',') : null,
    mobile_product_slider_images: form.mobileProductSliderImages.length ? form.mobileProductSliderImages.join(',') : null,
    mobile_size_chart_first: form.mobileSizeChartFirst || null,
    size_chart_img_1: form.sizeChartImg1 || null,
    size_chart_img_2: form.sizeChartImg2 || null,
    is_active: true,
    type: 'normal',
    variants: form.variants.map((variant) => ({
        size: variant.size, color: variant.color, color_hex: variant.color_hex,
        stock_quantity: variant.stock_quantity,
        width_cm: variant.width_cm || null, height_cm: variant.height_cm || null,
        preview_image: variant.preview_image || null, images: variant.images || null,
    })),
});
