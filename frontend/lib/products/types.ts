export interface AdminProductSummary {
    id: number;
    title: string;
    price: number;
    is_active: boolean;
}

export interface ProductData {
    id: number;
    title: string;
    price: number;
    old_price?: number;
    description?: string;
    weight?: number;
    stock_quantity?: number;
    desktop_video?: string;
    desktop_video_poster?: string;
    desktop_card_images?: string;
    desktop_slider_images?: string;
    mobile_card_image?: string;
    mobile_video_poster?: string;
    mobile_slider_images?: string;
    mobile_product_slider_images?: string;
    mobile_size_chart_first?: string;
    size_chart_img_1?: string;
    size_chart_img_2?: string;
    height?: number;
    width?: number;
    length?: number;
    variants?: Array<{
        id: number;
        size: string;
        color: string;
        color_hex?: string;
        stock_quantity: number;
        width_cm?: number | null;
        height_cm?: number | null;
        preview_image?: string;
        images?: string;
    }>;
    video_src?: string;
    image_left?: string;
    image_right?: string;
    gallery_images?: string;
    sizes?: string;
}

export type CatalogProduct = Pick<ProductData,
    'id' | 'title' | 'price' | 'old_price' | 'video_src' | 'desktop_video' | 'desktop_video_poster'
    | 'image_left' | 'image_right' | 'mobile_card_image' | 'mobile_video_poster' | 'mobile_slider_images'
>;

export interface ProductVariantData {
    id?: number;
    size: string;
    color: string;
    color_hex: string;
    stock_quantity: number;
    width_cm?: number | null;
    height_cm?: number | null;
    preview_image: string;
    images: string;
}

export type ProductVariantResponse = {
    id?: number;
    size?: string | null;
    color?: string | null;
    color_hex?: string | null;
    stock_quantity?: number | null;
    width_cm?: number | null;
    height_cm?: number | null;
    preview_image?: string | null;
    images?: string | null;
};

export type AdminProductFormResponse = {
    title?: string | null;
    price?: number | null;
    old_price?: number | null;
    description?: string | null;
    weight?: number | null;
    height?: number | null;
    width?: number | null;
    length?: number | null;
    stock_quantity?: number | null;
    desktop_video?: string | null;
    desktop_video_poster?: string | null;
    desktop_card_images?: string | null;
    desktop_slider_images?: string | null;
    mobile_card_image?: string | null;
    mobile_video_poster?: string | null;
    mobile_slider_images?: string | null;
    mobile_product_slider_images?: string | null;
    mobile_size_chart_first?: string | null;
    size_chart_img_1?: string | null;
    size_chart_img_2?: string | null;
    variants?: ProductVariantResponse[] | null;
};

export type AdminProductPayload = {
    title: string;
    price: number;
    old_price: number | null;
    description: string | null;
    weight: number;
    height: number;
    width: number;
    length: number;
    stock_quantity: number;
    desktop_video: string | null;
    desktop_video_poster: string | null;
    desktop_card_images: string | null;
    desktop_slider_images: string | null;
    mobile_card_image: string | null;
    mobile_video_poster: string | null;
    mobile_slider_images: string | null;
    mobile_product_slider_images: string | null;
    mobile_size_chart_first: string | null;
    size_chart_img_1: string | null;
    size_chart_img_2: string | null;
    is_active: true;
    type: 'normal';
    variants: Array<{
        size: string;
        color: string;
        color_hex: string;
        stock_quantity: number;
        width_cm: number | null;
        height_cm: number | null;
        preview_image: string | null;
        images: string | null;
    }>;
};
