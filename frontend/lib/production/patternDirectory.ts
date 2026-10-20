import type { Pattern } from './assortmentTypes.ts';
import {
    isReferenceChoice,
    isReferenceCount,
    isReferenceDecimal,
    isReferenceId,
    readReferencePage,
    requestDirectoryPage,
    type DirectoryQuery,
    type ReferenceChoice,
} from './referenceDirectory.ts';

export type PatternModel = ReferenceChoice & { version: number };
export type PatternModelCard = PatternModel & {
    pattern_count: number;
    uploaded_count: number;
    required_count: string;
};
export type PatternFile = Pattern & {
    garment_model_name: string;
    size_code: string;
    size_is_active: boolean;
};
export type PatternSize = {
    id: number;
    code: string;
    is_active: boolean;
    version: number;
    min_width_cm: string | null;
    max_width_cm: string | null;
    min_length_cm: string | null;
    max_length_cm: string | null;
    allow_standard_sleeve: boolean;
    allow_height_sleeve: boolean;
};
export type PatternContext = {
    model: PatternModel;
    size: PatternSize | null;
    pattern: Pattern | null;
};
export type PatternCoverage = PatternContext & {
    step_cm: string;
    width_values: string[];
    length_values: string[];
    width_page: number;
    length_page: number;
    width_pages: number;
    length_pages: number;
    width_count: number;
    length_count: number;
    required_count: string;
    uploaded_count: number;
    items: Pattern[];
};
export function readPatternUpload(value: unknown): {
    id: number;
    filename?: string;
} {
    const row = value as { id: number; filename?: string } | null;
    if (
        !row ||
        !isReferenceId(row.id) ||
        (row.filename !== undefined &&
            (typeof row.filename !== 'string' || !row.filename.trim()))
    )
        throw new Error('Сервер не подтвердил загрузку файла лекала.');
    return row;
}
export const slotCount = (value: unknown): value is string =>
    typeof value === 'string' && /^\d{1,20}$/.test(value);
export const patternSlot = (width: string, length: string, variant: string) =>
    `${Number(width).toFixed(2)}:${Number(length).toFixed(2)}:${variant}`;
export const sleeveVariants = (size: PatternSize) => [
    ...(size.allow_standard_sleeve ? ['standard' as const] : []),
    ...(size.allow_height_sleeve ? ['height' as const] : []),
];
const dimension = (value: unknown) =>
    isReferenceDecimal(value) && Number(value) > 0;
const nullableDimension = (value: unknown) =>
    value === null || dimension(value);
const validPattern = (row: Pattern) =>
    row &&
    isReferenceId(row.id) &&
    isReferenceId(row.version) &&
    isReferenceId(row.garment_model_id) &&
    isReferenceId(row.garment_size_id) &&
    isReferenceId(row.media_object_id) &&
    typeof row.code === 'string' &&
    typeof row.name === 'string' &&
    typeof row.grid_key === 'string' &&
    typeof row.is_active === 'boolean' &&
    ['standard', 'height'].includes(row.sleeve_variant) &&
    dimension(row.width_cm) &&
    dimension(row.length_cm);
export const readPatternModels = (value: unknown) =>
    readReferencePage<PatternModelCard>(
        value,
        (row) =>
            isReferenceChoice(row) &&
            isReferenceId(row.version) &&
            isReferenceCount(row.pattern_count) &&
            isReferenceCount(row.uploaded_count) &&
            slotCount(row.required_count),
    );
export const readPatternFiles = (value: unknown) =>
    readReferencePage<PatternFile>(
        value,
        (row) =>
            validPattern(row) &&
            typeof row.garment_model_name === 'string' &&
            typeof row.size_code === 'string' &&
            typeof row.size_is_active === 'boolean',
    );
export function readPatternContext(value: unknown): PatternContext {
    const row = value as PatternContext | null,
        size = row?.size;
    if (
        !row ||
        !isReferenceChoice(row.model) ||
        !isReferenceId(row.model.version)
    )
        throw new Error('Не удалось прочитать модель лекала.');
    if (
        size !== null &&
        (!size ||
            !isReferenceId(size.id) ||
            !isReferenceId(size.version) ||
            typeof size.code !== 'string' ||
            typeof size.is_active !== 'boolean' ||
            ![
                size.min_width_cm,
                size.max_width_cm,
                size.min_length_cm,
                size.max_length_cm,
            ].every(nullableDimension) ||
            typeof size.allow_standard_sleeve !== 'boolean' ||
            typeof size.allow_height_sleeve !== 'boolean' ||
            !sleeveVariants(size).length)
    )
        throw new Error('Сервер вернул неверный размер лекала.');
    if (
        row.pattern !== null &&
        (!validPattern(row.pattern) ||
            row.pattern.garment_model_id !== row.model.id ||
            row.pattern.garment_size_id !== size?.id)
    )
        throw new Error('Сервер вернул лекало другой модели или размера.');
    return row;
}
export function readPatternCoverage(value: unknown): PatternCoverage {
    const context = readPatternContext(value),
        row = value as PatternCoverage;
    if (
        row.pattern !== null ||
        row.step_cm !== '2.00' ||
        !slotCount(row.required_count) ||
        !isReferenceCount(row.uploaded_count) ||
        ![
            row.width_page,
            row.length_page,
            row.width_pages,
            row.length_pages,
            row.width_count,
            row.length_count,
        ].every(isReferenceCount) ||
        ![row.width_values, row.length_values].every(
            (axis) =>
                Array.isArray(axis) &&
                axis.length <= 6 &&
                axis.every(dimension),
        ) ||
        !Array.isArray(row.items) ||
        row.items.length > 72
    )
        throw new Error('Сервер вернул неверный участок сетки лекал.');
    for (const axis of ['width', 'length'] as const) {
        const values = row[`${axis}_values`],
            page = row[`${axis}_page`],
            pages = row[`${axis}_pages`],
            count = row[`${axis}_count`];
        if (
            pages !== Math.ceil(count / 6) ||
            (pages ? page >= pages : page !== 0) ||
            values.length !== Math.min(6, Math.max(0, count - page * 6))
        )
            throw new Error('Неверная страница сетки лекал.');
        const minimum =
            context.size?.[`min_${axis === 'width' ? 'width' : 'length'}_cm`];
        if (
            values.some(
                (value, index) =>
                    Math.round(Number(value) * 100) !==
                    Math.round(Number(minimum) * 100) +
                        (page * 6 + index) * 200,
            )
        )
            throw new Error('Нарушен шаг сетки лекал.');
    }
    const ids = new Set<number>(),
        slots = new Set<string>();
    for (const item of row.items) {
        const slot = patternSlot(
            item.width_cm,
            item.length_cm,
            item.sleeve_variant,
        );
        if (
            !validPattern(item) ||
            item.garment_model_id !== context.model.id ||
            item.garment_size_id !== context.size?.id ||
            !row.width_values.includes(item.width_cm) ||
            !row.length_values.includes(item.length_cm) ||
            !sleeveVariants(context.size).includes(item.sleeve_variant) ||
            ids.has(item.id) ||
            slots.has(slot)
        )
            throw new Error('Сервер вернул неверную клетку лекала.');
        ids.add(item.id);
        slots.add(slot);
    }
    return row;
}
export const requestPatternModels = (
    query: DirectoryQuery,
    signal: AbortSignal,
) => requestDirectoryPage('pattern-models', query, readPatternModels, signal);
export const requestPatternFiles = (
    query: DirectoryQuery,
    signal: AbortSignal,
) => requestDirectoryPage('patterns', query, readPatternFiles, signal);
export const requestPatternSizes = (
    query: DirectoryQuery,
    signal: AbortSignal,
) =>
    requestDirectoryPage(
        'pattern-sizes',
        query,
        (value) => readReferencePage<ReferenceChoice>(value, isReferenceChoice),
        signal,
    );
