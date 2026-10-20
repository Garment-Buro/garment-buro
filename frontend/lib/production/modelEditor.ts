import type { GarmentSize } from './assortmentTypes.ts';
import type { ModelDetail } from './referenceDirectory.ts';
import { compactDecimal } from './numbers.ts';
export const MODEL_SIZE_LIMIT = 100;
export type ModelEditor = Omit<ModelDetail, 'id' | 'version'> & {
    id?: number;
    version?: number;
    size_chart_url?: string | null;
};
export const emptySize = (sortOrder: number): GarmentSize => ({
    code: '',
    sort_order: sortOrder,
    base_price: '0',
    base_length_cm: null,
    base_width_cm: null,
    min_height_cm: null,
    max_height_cm: null,
    min_length_cm: null,
    max_length_cm: null,
    min_width_cm: null,
    max_width_cm: null,
    min_sleeve_length_cm: null,
    max_sleeve_length_cm: null,
    allow_standard_sleeve: true,
    allow_height_sleeve: true,
    extra_width_price_per_cm: null,
});
export const emptyModel = (): ModelEditor => ({
    category_id: null,
    code: '',
    name: '',
    description: null,
    base_size_code: null,
    fit_model_name: null,
    fit_model_height_cm: null,
    base_weight_g: null,
    size_chart_media_object_id: null,
    is_active: true,
    sizes: [emptySize(0)],
});
const dimensionFields = [
    'base_length_cm',
    'base_width_cm',
    'min_height_cm',
    'max_height_cm',
    'min_length_cm',
    'max_length_cm',
    'min_width_cm',
    'max_width_cm',
    'min_sleeve_length_cm',
    'max_sleeve_length_cm',
    'extra_width_price_per_cm',
] as const;
const compactNullable = (value: string | null | undefined) =>
    value == null ? null : compactDecimal(value);
export const modelChartUrl = (id: number) =>
    `/api/production/admin/assortment/media/public/${id}`;
export function toModelEditor(model: ModelDetail): ModelEditor {
    const sizes = model.sizes.filter((size) => size.is_active !== false);
    if (sizes.length > MODEL_SIZE_LIMIT)
        throw new Error(
            `У модели больше ${MODEL_SIZE_LIMIT} активных размеров. Нужна проверка размерной сетки.`,
        );
    return {
        ...model,
        fit_model_height_cm: compactNullable(model.fit_model_height_cm),
        base_weight_g: compactNullable(model.base_weight_g),
        size_chart_url:
            model.size_chart_media_object_id === null
                ? null
                : modelChartUrl(model.size_chart_media_object_id),
        sizes: sizes.map((size) => ({
            ...size,
            base_price: compactDecimal(size.base_price),
            ...Object.fromEntries(
                dimensionFields.map((field) => [
                    field,
                    compactNullable(size[field]),
                ]),
            ),
        })),
    };
}
// Keep decimal strings exact; the server validates the business ranges.
function decimal(value: string | null | undefined): string | null {
    if (value == null || value === '') return null;
    const text = compactDecimal(value);
    if (!/^\d+(?:\.\d{1,2})?$/.test(text))
        throw new Error(
            'Укажите неотрицательные числа, не более двух знаков после запятой.',
        );
    return text;
}
export function buildModelPayload(editor: ModelEditor) {
    if (!editor.sizes.length || editor.sizes.length > MODEL_SIZE_LIMIT)
        throw new Error(
            `В модели должно быть от 1 до ${MODEL_SIZE_LIMIT} размеров.`,
        );
    if (
        editor.id &&
        (!Number.isSafeInteger(editor.version) || (editor.version ?? 0) < 1)
    )
        throw new Error(
            'Не удалось определить версию модели. Перечитайте модель.',
        );
    return {
        ...(editor.id ? { expected_version: editor.version } : {}),
        category_id: editor.category_id,
        code: editor.code,
        name: editor.name,
        description: editor.description,
        base_size_code: editor.base_size_code,
        fit_model_name: editor.fit_model_name,
        fit_model_height_cm: decimal(editor.fit_model_height_cm),
        base_weight_g: decimal(editor.base_weight_g),
        size_chart_media_object_id: editor.size_chart_media_object_id,
        is_active: editor.is_active,
        sizes: editor.sizes.map((size, index) => ({
            code: size.code,
            sort_order: index,
            base_price: decimal(size.base_price) ?? '0',
            ...Object.fromEntries(
                dimensionFields.map((field) => [field, decimal(size[field])]),
            ),
            allow_standard_sleeve: size.allow_standard_sleeve,
            allow_height_sleeve: size.allow_height_sleeve,
            currency: 'RUB',
        })),
    };
}
export function readModelUpload(value: unknown): {
    id: number;
    url: string;
} {
    if (
        value === null ||
        typeof value !== 'object' ||
        !('id' in value) ||
        typeof value.id !== 'number' ||
        !Number.isSafeInteger(value.id) ||
        value.id < 1
    )
        throw new Error(
            'Сервер не подтвердил загрузку таблицы размеров. Повторите загрузку.',
        );
    return { id: value.id, url: modelChartUrl(value.id) };
}
