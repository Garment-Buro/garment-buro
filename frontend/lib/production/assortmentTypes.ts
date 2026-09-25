export type AssortmentSection =
    | 'models'
    | 'patterns'
    | 'techCards'
    | 'fabrics'
    | 'accessories'
    | 'boxes'
    | 'products';

export interface GarmentSize {
    id?: number;
    code: string;
    sort_order: number;
    base_price: string;
    base_length_cm: string | null;
    base_width_cm: string | null;
    min_height_cm: string | null;
    max_height_cm: string | null;
    min_length_cm: string | null;
    max_length_cm: string | null;
    min_width_cm: string | null;
    max_width_cm: string | null;
    min_sleeve_length_cm: string | null;
    max_sleeve_length_cm: string | null;
    allow_standard_sleeve: boolean;
    allow_height_sleeve: boolean;
    extra_width_price_per_cm?: string | null;
    currency?: string;
    is_active?: boolean;
    version?: number;
}

export interface GarmentModel {
    id: number;
    category_id: number | null;
    code: string;
    name: string;
    description: string | null;
    base_size_code: string | null;
    fit_model_name: string | null;
    fit_model_height_cm: string | null;
    base_weight_g: string | null;
    size_chart_media_object_id: number | null;
    is_active: boolean;
    version: number;
    catalog_product_ids: number[];
    sizes: GarmentSize[];
    published_tech_card: {
        tech_card_id: number;
        revision_number: number;
        name: string;
    } | null;
}

export interface GarmentModelCategory {
    id: number;
    code: string;
    name: string;
    is_active: boolean;
    version: number;
}

export interface ReferencePage<T> {
    items: T[];
    next_cursor: number | null;
    limit: number;
}

export interface Fabric {
    id: number;
    code: string;
    name: string;
    material_type: string | null;
    color_name: string;
    color_hex: string | null;
    density_gsm: string | null;
    width_cm: string;
    cost_per_kg: string | null;
    minimum_stock_meters: string;
    currency: string;
    is_active: boolean;
    version: number;
    balance: { available_quantity: string; on_hand_quantity: string } | null;
}

export interface Pattern {
    id: number;
    code: string;
    garment_model_id: number;
    garment_size_id: number;
    media_object_id: number;
    name: string;
    sleeve_variant: 'standard' | 'height';
    width_cm: string;
    length_cm: string;
    grid_key: string;
    is_active: boolean;
    version: number;
}

export interface FabricRequirement {
    id: number;
    garment_model_id: number;
    fabric_id: number;
    meters_per_unit: string;
    waste_percent: string;
    is_primary: boolean;
    version: number;
}

export interface TechCheckpoint {
    id?: number;
    position: number;
    stage_code: string;
    role_code: string;
    name: string;
    description: string | null;
    standard_minutes: string | null;
    labor_cost: string;
    currency: string;
}

export interface TechRevision {
    id: number;
    revision_number: number;
    status: 'draft' | 'published' | 'archived' | 'discarded';
    name_snapshot: string;
    description_snapshot: string | null;
    checkpoints: TechCheckpoint[];
    published_at: string | null;
}

export interface TechCard {
    id: number;
    garment_model_id: number;
    code: string;
    latest_revision_number: number;
    is_active: boolean;
    revisions: TechRevision[];
}

export interface AccessoryCategory {
    id: number;
    code: string;
    name: string;
    description: string | null;
    is_active: boolean;
    version: number;
}

export interface Accessory {
    id: number;
    category_id: number;
    code: string;
    name: string;
    unit_cost: string;
    currency: string;
    stock_quantity: number;
    minimum_stock_quantity: number;
    photo_media_object_id: number | null;
    is_active: boolean;
    version: number;
    model_ids: number[];
}

export interface AccessoryRequirement {
    id: number;
    garment_model_id: number;
    accessory_id: number;
    quantity_per_unit: string;
    is_optional: boolean;
    notes: string | null;
    version: number;
}

export interface PackagingBox {
    id: number;
    code: string;
    name: string;
    inner_length_cm: string;
    inner_width_cm: string;
    inner_height_cm: string;
    max_items: number;
    unit_cost: string;
    currency: string;
    stock_quantity: number;
    minimum_stock_quantity: number;
    photo_media_object_id: number | null;
    is_active: boolean;
    version: number;
}

export interface PackagingRule {
    id: number;
    garment_model_id: number;
    box_id: number;
    max_items: number;
    priority: number;
    version: number;
}

export interface ProductVariantReference {
    id: number;
    sku: string | null;
    size: string | null;
    garment_size_id: number | null;
    fabric_id: number | null;
    color: string | null;
    stock_quantity: number;
}

export interface ProductReference {
    id: number;
    title: string;
    slug: string | null;
    category_id: number | null;
    garment_model_id: number | null;
    price: string;
    old_price: string | null;
    image_url: string | null;
    is_active: boolean;
    stock_quantity: number;
    variants: ProductVariantReference[];
}

export interface ProductCategory {
    id: number;
    slug: string;
    name: string;
    description: string | null;
    is_active: boolean;
    version: number;
}

export interface ProductCommunity {
    id: number;
    title: string;
    slug: string;
    image_url: string | null;
    status: string;
    partner_name: string;
    product_ids: number[];
}

export interface ProductDetail {
    id: number;
    title: string;
    price: number;
    old_price: number | null;
    description: string | null;
    composition: string | null;
    model_info: string | null;
    sizes: string;
    colors: string;
    is_active: boolean;
    type: string;
    weight: number;
    height: number;
    width: number;
    length: number;
    stock_quantity: number;
    video_src: string | null;
    image_left: string | null;
    image_right: string | null;
    gallery_images: string | null;
    size_chart_img_1: string | null;
    size_chart_img_2: string | null;
    desktop_video: string | null;
    desktop_video_poster: string | null;
    desktop_card_images: string | null;
    desktop_slider_images: string | null;
    mobile_card_image: string | null;
    mobile_video_poster: string | null;
    mobile_slider_images: string | null;
    mobile_product_slider_images: string | null;
    mobile_size_chart_first: string | null;
    variants: Array<{
        id: number;
        size: string | null;
        color: string | null;
        color_hex: string | null;
        stock_quantity: number;
        width_cm: number | null;
        height_cm: number | null;
        preview_image: string | null;
        images: string | null;
    }>;
}

export const assortmentLabels: Record<AssortmentSection, string> = {
    models: 'Модели',
    patterns: 'Лекала',
    techCards: 'Техкарты',
    fabrics: 'Ткани',
    accessories: 'Фурнитура',
    boxes: 'Коробки',
    products: 'Товары',
};
