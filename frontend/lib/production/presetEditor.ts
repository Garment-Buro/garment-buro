import type { ProductDetail } from './assortmentTypes.ts';

import type { EditorModel, EditorFabric } from '../products/editorClient.ts';

export const PRESET_VARIANT_LIMIT = 200;

export type PresetEditor = ProductDetail & { tagsText: string };

export function buildPresetPayload(editor: PresetEditor) {
    if (editor.variants.length > PRESET_VARIANT_LIMIT)
        throw new Error(
            `В одном пресете можно сохранить не более ${PRESET_VARIANT_LIMIT} вариантов.`,
        );
    return {
        ...(editor.id ? { expected_version: editor.version } : {}),
        title: editor.title,
        preset_source: editor.preset_source,
        tags: editor.tagsText
            .split(',')
            .map((tag) => tag.trim())
            .filter(Boolean),
        slug: editor.slug || null,
        category_id: editor.category_id,
        garment_model_id: editor.garment_model_id,
        price: Number(editor.price),
        old_price: editor.old_price == null ? null : Number(editor.old_price),
        description: editor.description,
        composition: editor.composition,
        model_info: editor.model_info,
        sizes: editor.sizes,
        colors: editor.colors,
        is_active: editor.is_active,
        type: editor.type,
        weight: Number(editor.weight),
        height: Number(editor.height),
        width: Number(editor.width),
        length: Number(editor.length),

        video_src: editor.video_src,
        image_left: editor.image_left,
        image_right: editor.image_right,
        gallery_images: editor.gallery_images,
        size_chart_img_1: editor.size_chart_img_1,
        size_chart_img_2: editor.size_chart_img_2,
        desktop_video: editor.desktop_video,
        desktop_video_poster: editor.desktop_video_poster,
        desktop_card_images: editor.desktop_card_images,
        desktop_slider_images: editor.desktop_slider_images,
        mobile_card_image: editor.mobile_card_image,
        mobile_video_poster: editor.mobile_video_poster,
        mobile_slider_images: editor.mobile_slider_images,
        mobile_product_slider_images: editor.mobile_product_slider_images,
        mobile_size_chart_first: editor.mobile_size_chart_first,
        stock_quantity: editor.stock_quantity,
        variants: editor.variants.map((variant) => ({
            id: variant.id || undefined,
            size: variant.size,
            garment_size_id: variant.garment_size_id,
            fabric_id: variant.fabric_id,
            color: variant.color,
            color_hex: variant.color_hex,
            stock_quantity: variant.stock_quantity,
            width_cm: variant.width_cm,
            height_cm: variant.height_cm,
            preview_image: variant.preview_image,
            images: variant.images,
        })),
    };
}

export function rebuildPresetVariants(
    variants: ProductDetail['variants'],
    model: EditorModel | undefined,
    fabrics: EditorFabric[],
    sizeIds: number[],
    fabricIds: number[],
): ProductDetail['variants'] {
    const key = (size: number | null, fabric: number | null) =>
        `${size ?? ''}:${fabric ?? ''}`;
    const existing = new Map<string, ProductDetail['variants']>();
    for (const variant of variants) {
        const id = key(variant.garment_size_id, variant.fabric_id);
        existing.set(id, [...(existing.get(id) ?? []), variant]);
    }
    const sizes = [...new Set(sizeIds)],
        materials = [...new Set(fabricIds)];
    if (!sizes.length && !materials.length) return [];
    const selectedSizes = sizes.length ? sizes : [null];
    const selectedMaterials = materials.length ? materials : [null];
    const tooMany = () =>
        new Error(
            `В одном пресете можно сохранить не более ${PRESET_VARIANT_LIMIT} вариантов. Сократите выбор размеров или тканей.`,
        );
    // Reject the Cartesian product before constructing variant objects.
    if (selectedSizes.length * selectedMaterials.length > PRESET_VARIANT_LIMIT)
        throw tooMany();
    let count = 0;
    for (const sizeId of selectedSizes)
        for (const fabricId of selectedMaterials) {
            count += existing.get(key(sizeId, fabricId))?.length ?? 1;
            if (count > PRESET_VARIANT_LIMIT) throw tooMany();
        }
    return selectedSizes.flatMap((sizeId) =>
        selectedMaterials.flatMap((fabricId) => {
            const previous = existing.get(key(sizeId, fabricId));
            if (previous) return previous;
            const size = model?.sizes.find((item) => item.id === sizeId);
            const fabric = fabrics.find((item) => item.id === fabricId);
            return [
                {
                    id: 0,
                    sku: null,
                    garment_size_id: sizeId,
                    fabric_id: fabricId,
                    size: size?.code ?? null,
                    color: fabric?.color_name ?? null,
                    color_hex: fabric?.color_hex ?? null,
                    stock_quantity: 0,
                    reserved_quantity: 0,
                    available_stock_quantity: 0,
                    width_cm: null,
                    height_cm: null,
                    preview_image: null,
                    images: null,
                },
            ];
        }),
    );
}

export const emptyPresetEditor = (): PresetEditor => ({
    id: 0,
    version: 1,
    title: '',
    preset_source: 'garment_buro',
    tags: [],
    tagsText: '',
    slug: '',
    category_id: null,
    garment_model_id: null,
    price: 0,
    old_price: null,
    description: null,
    composition: null,
    model_info: null,
    sizes: '',
    colors: '',
    is_active: true,
    type: 'normal',
    weight: 0,
    height: 0,
    width: 0,
    length: 0,
    stock_quantity: 0,
    reserved_quantity: 0,
    available_stock_quantity: 0,
    video_src: null,
    image_left: null,
    image_right: null,
    gallery_images: null,
    size_chart_img_1: null,
    size_chart_img_2: null,
    desktop_video: null,
    desktop_video_poster: null,
    desktop_card_images: null,
    desktop_slider_images: null,
    mobile_card_image: null,
    mobile_video_poster: null,
    mobile_slider_images: null,
    mobile_product_slider_images: null,
    mobile_size_chart_first: null,
    variants: [],
});
