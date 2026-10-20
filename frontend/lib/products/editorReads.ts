import type { ProductDetail } from '../production/assortmentTypes.ts';
import type {
    EditorFabric,
    EditorModel,
    EditorModelOption,
    EditorOptionPage,
    EditorQuery,
    EditorSize,
} from './editorClient.ts';

type Row = Record<string, unknown>;
const object = (value: unknown): value is Row =>
    value !== null && typeof value === 'object' && !Array.isArray(value);
const id = (value: unknown): value is number =>
    typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
const count = (value: unknown) =>
    typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
const amount = (value: unknown) =>
    typeof value === 'number' && Number.isFinite(value) && value >= 0;
const nullable = (value: unknown, valid: (value: unknown) => boolean) =>
    value === null || valid(value);
const text = (value: unknown) => typeof value === 'string';
const fail = (message: string): never => {
    throw new Error(message);
};
const nullableTexts = [
    'slug',
    'description',
    'composition',
    'model_info',
    'video_src',
    'image_left',
    'image_right',
    'gallery_images',
    'size_chart_img_1',
    'size_chart_img_2',
    'desktop_video',
    'desktop_video_poster',
    'desktop_card_images',
    'desktop_slider_images',
    'mobile_card_image',
    'mobile_video_poster',
    'mobile_slider_images',
    'mobile_product_slider_images',
    'mobile_size_chart_first',
] as const;
const variantTexts = [
    'sku',
    'size',
    'color',
    'color_hex',
    'preview_image',
    'images',
] as const;

export function readPresetDetail(
    value: unknown,
    requestedId: number,
): ProductDetail {
    const invalid = () =>
        fail(
            'Сервер вернул неполные или неверные данные пресета. Повторите загрузку.',
        );
    if (
        !object(value) ||
        value.id !== requestedId ||
        !id(value.id) ||
        !id(value.version) ||
        !['title', 'sizes', 'colors', 'type'].every((key) =>
            text(value[key]),
        ) ||
        typeof value.is_active !== 'boolean' ||
        (value.preset_source !== 'garment_buro' &&
            value.preset_source !== 'user') ||
        !Array.isArray(value.tags) ||
        !value.tags.every(text) ||
        !['category_id', 'garment_model_id'].every((key) =>
            nullable(value[key], id),
        ) ||
        !['price', 'weight', 'height', 'width', 'length'].every((key) =>
            amount(value[key]),
        ) ||
        !nullable(value.old_price, amount) ||
        ![
            'stock_quantity',
            'reserved_quantity',
            'available_stock_quantity',
        ].every((key) => count(value[key])) ||
        !nullableTexts.every((key) => nullable(value[key], text)) ||
        !Array.isArray(value.variants)
    )
        return invalid();
    if (value.variants.length > 200)
        return fail(
            'У пресета больше 200 вариантов. Нужна проверка его состава перед редактированием.',
        );
    const seen = new Set<number>();
    for (const row of value.variants) {
        if (
            !object(row) ||
            !id(row.id) ||
            seen.has(row.id) ||
            !['garment_size_id', 'fabric_id'].every((key) =>
                nullable(row[key], id),
            ) ||
            !variantTexts.every((key) => nullable(row[key], text)) ||
            ![
                'stock_quantity',
                'reserved_quantity',
                'available_stock_quantity',
            ].every((key) => count(row[key])) ||
            !['width_cm', 'height_cm'].every((key) =>
                nullable(row[key], amount),
            )
        )
            return invalid();
        seen.add(row.id);
    }
    // Every field consumed by the editor was checked; no defaults hide missing server data.
    return value as unknown as ProductDetail;
}

const option = (value: unknown): value is EditorModelOption =>
    object(value) &&
    id(value.id) &&
    typeof value.name === 'string' &&
    typeof value.is_active === 'boolean';
const fabric = (value: unknown): value is EditorFabric =>
    option(value) &&
    object(value) &&
    typeof value.color_name === 'string' &&
    nullable(value.color_hex, text);
const sizeOption = (value: unknown): value is EditorSize =>
    object(value) &&
    id(value.id) &&
    typeof value.code === 'string' &&
    typeof value.is_active === 'boolean';

export function readEditorModel(
    value: unknown,
    requestedId: number,
    requestedSizeIds: number[] = [],
): EditorModel {
    if (
        !option(value) ||
        value.id !== requestedId ||
        !object(value) ||
        !Array.isArray(value.sizes)
    )
        return fail(
            'Сервер вернул неполные или неверные данные модели пресета.',
        );
    const seen = new Set<number>();
    const wanted = new Set(requestedSizeIds);
    if (value.sizes.length !== wanted.size || value.sizes.length > 200)
        return fail(
            'Сервер вернул не все выбранные размеры. Повторите загрузку.',
        );
    for (const size of value.sizes) {
        if (!sizeOption(size) || !wanted.has(size.id) || seen.has(size.id))
            return fail(
                'Сервер вернул неверную размерную сетку модели пресета.',
            );
        seen.add(size.id);
    }
    return value as unknown as EditorModel;
}

function readPage<T extends { id: number }>(
    value: unknown,
    valid: (row: unknown) => row is T,
    query: EditorQuery,
): EditorOptionPage<T> {
    if (
        !object(value) ||
        !Array.isArray(value.items) ||
        value.items.length > (query.limit ?? 24) ||
        !nullable(value.next_cursor, id)
    )
        return fail('Сервер вернул неверную страницу вариантов пресета.');
    let previous = Number(query.cursor ?? 0);
    for (const row of value.items) {
        if (!valid(row) || row.id <= previous)
            return fail('Сервер вернул неверную запись вариантов пресета.');
        previous = row.id;
    }
    if (
        value.next_cursor !== null &&
        (!value.items.length || value.next_cursor !== previous)
    )
        return fail('Сервер вернул неверное продолжение вариантов пресета.');
    return value as unknown as EditorOptionPage<T>;
}
export const readModelOptions = (value: unknown, query: EditorQuery) =>
    readPage(value, option, query);
export const readFabricOptions = (value: unknown, query: EditorQuery) =>
    readPage(value, fabric, query);
export const readSizeOptions = (value: unknown, query: EditorQuery) =>
    readPage(value, sizeOption, query);

export function readSelectedFabrics(
    value: unknown,
    requestedIds: number[],
): EditorFabric[] {
    const wanted = new Set(requestedIds);
    if (
        !Array.isArray(value) ||
        value.length !== wanted.size ||
        value.length > 200
    )
        return fail(
            'Сервер вернул не все выбранные ткани. Повторите загрузку.',
        );
    const seen = new Set<number>();
    for (const row of value) {
        if (!fabric(row) || !wanted.has(row.id) || seen.has(row.id))
            return fail(
                'Сервер вернул неверные данные выбранной ткани. Повторите загрузку.',
            );
        seen.add(row.id);
    }
    return value;
}

export function readPresetUpload(value: unknown): string {
    const invalid = () =>
        fail('Сервер не подтвердил загрузку изображения. Повторите загрузку.');
    if (
        !object(value) ||
        !id(value.id) ||
        typeof value.url !== 'string' ||
        !value.url ||
        /[\s,\\\u0000-\u001f\u007f]/.test(value.url)
    )
        return invalid();
    try {
        const relative =
            value.url.startsWith('/') && !value.url.startsWith('//');
        if (!relative && !/^https?:\/\//i.test(value.url)) return invalid();
        const url = new URL(value.url, 'https://media.invalid');
        if (
            !['https:', 'http:'].includes(url.protocol) ||
            url.username ||
            url.password
        )
            return invalid();
        return value.url;
    } catch {
        return invalid();
    }
}
