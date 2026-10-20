import { ApiError, requestReadJson } from '../api/http.ts';
import { PageCursorExpiredError } from '../catalog/pagedResource.ts';
import type {
    Fabric,
    FabricRequirement,
    GarmentModel,
} from './assortmentTypes.ts';

export type ModelCard = Pick<
    GarmentModel,
    'id' | 'category_id' | 'code' | 'name' | 'is_active' | 'base_weight_g'
> & {
    category_name: string | null;
    size_count: number;
    product_count: number;
    tech_card_name: string | null;
    tech_card_revision: number | null;
};
export type ModelDetail = Omit<
    GarmentModel,
    'catalog_product_ids' | 'published_tech_card'
>;
export type FabricRequirementCard = FabricRequirement & {
    garment_model_name: string;
    fabric_name: string;
};
export type ReferenceKind =
    | 'models'
    | 'fabrics'
    | 'accessories'
    | 'boxes'
    | 'accessory-categories'
    | 'tech-card-models'
    | 'pattern-sizes'
    | 'model-categories'
    | 'product-categories';
export type ReferenceChoice = {
    id: number;
    name: string;
    code: string;
    is_active: boolean;
    max_items?: number | null;
};
export type ReferencePage<T> = { items: T[]; next_cursor: string | null };
export type DirectoryQuery = {
    query?: string;
    active?: boolean;
    category_id?: number | null;
    stock?: string;
    revision_status?: string;
    model_id?: number | null;
    size_id?: number | null;
    pattern_active?: boolean;
    sort?: string;
    limit?: number;
    cursor?: string | null;
};
export const referenceSearch = (query: DirectoryQuery) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query))
        if (value != null && value !== '') params.set(key, String(value));
    params.sort();
    return params.toString();
};
export const isReferenceId = (value: unknown) =>
    Number.isSafeInteger(value) &&
    Number(value) > 0 &&
    Number(value) <= 2147483647;
export const isReferenceDecimal = (value: unknown) =>
    typeof value === 'string' &&
    /^-?\d+(?:\.\d+)?$/.test(value) &&
    Number.isFinite(Number(value));
const nullableDecimal = (value: unknown) =>
    value === null || isReferenceDecimal(value);
export const isReferenceCount = (value: unknown) =>
    Number.isSafeInteger(value) && Number(value) >= 0;
export const isReferenceChoice = (row: ReferenceChoice) =>
    row &&
    isReferenceId(row.id) &&
    typeof row.name === 'string' &&
    typeof row.code === 'string' &&
    typeof row.is_active === 'boolean';
export function readReferencePage<T extends { id: number }>(
    value: unknown,
    valid: (row: T) => boolean,
): ReferencePage<T> {
    const page = value as ReferencePage<T> | null;
    if (
        !page ||
        !Array.isArray(page.items) ||
        page.items.length > 100 ||
        !(
            page.next_cursor === null ||
            (typeof page.next_cursor === 'string' &&
                page.next_cursor.length > 0 &&
                page.next_cursor.length <= 2048)
        )
    )
        throw new Error('Сервер вернул неверную страницу справочника.');
    const seen = new Set<number>();
    for (const row of page.items) {
        if (!row || !isReferenceId(row.id) || seen.has(row.id) || !valid(row))
            throw new Error('Сервер вернул неверную запись справочника.');
        seen.add(row.id);
    }
    return page;
}
export const readModelPage = (value: unknown) =>
    readReferencePage<ModelCard>(
        value,
        (row) =>
            isReferenceChoice(row) &&
            (row.category_id === null || isReferenceId(row.category_id)) &&
            (row.category_name === null || typeof row.category_name === 'string') &&
            isReferenceCount(row.size_count) &&
            isReferenceCount(row.product_count) &&
            nullableDecimal(row.base_weight_g) &&
            (row.tech_card_name === null ||
                typeof row.tech_card_name === 'string') &&
            (row.tech_card_revision === null ||
                isReferenceId(row.tech_card_revision)),
    );
function validFabric(row: Fabric): boolean {
    if (
        !isReferenceChoice(row) ||
        !isReferenceId(row.version) ||
        row.currency !== 'RUB' ||
        typeof row.color_name !== 'string'
    )
        return false;
    if (
        ![row.material_type, row.color_hex].every(
            (value) => value === null || typeof value === 'string',
        )
    )
        return false;
    if (![row.width_cm, row.minimum_stock_meters].every(isReferenceDecimal))
        return false;
    if (
        ![row.density_gsm, row.cost_per_kg, row.cost_per_meter].every(
            nullableDecimal,
        )
    )
        return false;
    const balance = row.balance;
    return (
        balance === null ||
        Boolean(
            balance &&
                [
                    balance.available_meters,
                    balance.on_hand_meters,
                    balance.reserved_meters,
                ].every(isReferenceDecimal) &&
                isReferenceId(balance.version) &&
                typeof balance.updated_at === 'string' &&
                Number.isFinite(Date.parse(balance.updated_at)),
        )
    );
}
export const readFabricPage = (value: unknown) =>
    readReferencePage<Fabric>(value, validFabric);
export const readRequirementPage = (value: unknown) =>
    readReferencePage<FabricRequirementCard>(
        value,
        (row) =>
            isReferenceId(row.version) &&
            isReferenceId(row.garment_model_id) &&
            isReferenceId(row.fabric_id) &&
            typeof row.garment_model_name === 'string' &&
            typeof row.fabric_name === 'string' &&
            isReferenceDecimal(row.meters_per_unit) &&
            isReferenceDecimal(row.waste_percent) &&
            typeof row.is_primary === 'boolean',
    );
export function readModelDetail(value: unknown): ModelDetail {
    const row = value as ModelDetail | null;
    const incomplete = () =>
        new Error('Сервер вернул неполную модель. Редактор не открыт.');
    if (
        !row ||
        !isReferenceChoice(row) ||
        !isReferenceId(row.version) ||
        !(row.category_id === null || isReferenceId(row.category_id))
    )
        throw incomplete();
    if (
        ![row.description, row.base_size_code, row.fit_model_name].every(
            (value) => value === null || typeof value === 'string',
        )
    )
        throw incomplete();
    if (![row.fit_model_height_cm, row.base_weight_g].every(nullableDecimal))
        throw incomplete();
    if (
        !(
            row.size_chart_media_object_id === null ||
            isReferenceId(row.size_chart_media_object_id)
        ) ||
        !Array.isArray(row.sizes)
    )
        throw incomplete();
    const ids = new Set<number>();
    for (const size of row.sizes) {
        if (
            !size ||
            !isReferenceId(size.id) ||
            ids.has(size.id!) ||
            typeof size.code !== 'string' ||
            !isReferenceCount(size.sort_order) ||
            !isReferenceId(size.version) ||
            typeof size.is_active !== 'boolean' ||
            typeof size.allow_standard_sleeve !== 'boolean' ||
            typeof size.allow_height_sleeve !== 'boolean' ||
            size.currency !== 'RUB' ||
            !isReferenceDecimal(size.base_price)
        )
            throw incomplete();
        ids.add(size.id!);
        const dimensions = [
            size.base_length_cm,
            size.base_width_cm,
            size.min_height_cm,
            size.max_height_cm,
            size.min_length_cm,
            size.max_length_cm,
            size.min_width_cm,
            size.max_width_cm,
            size.min_sleeve_length_cm,
            size.max_sleeve_length_cm,
            size.extra_width_price_per_cm,
        ];
        if (!dimensions.every(nullableDecimal)) throw incomplete();
    }
    return row;
}
const root = '/production/admin/assortment';
export async function requestDirectoryPage<T>(
    kind: string,
    query: DirectoryQuery,
    read: (value: unknown) => T,
    signal: AbortSignal,
) {
    try {
        return read(
            await requestReadJson<unknown>(
                `${root}/directory/${kind}?${referenceSearch(query)}`,
                { signal, cache: 'no-store' },
            ),
        );
    } catch (error) {
        if (
            error instanceof ApiError &&
            error.status === 422 &&
            error.code === 'invalid_cursor'
        )
            throw new PageCursorExpiredError();
        throw error;
    }
}
export const requestModelPage = (query: DirectoryQuery, signal: AbortSignal) =>
    requestDirectoryPage('models', query, readModelPage, signal);
export const requestFabricPage = (query: DirectoryQuery, signal: AbortSignal) =>
    requestDirectoryPage('fabrics', query, readFabricPage, signal);
export const requestRequirementPage = (
    query: DirectoryQuery,
    signal: AbortSignal,
) =>
    requestDirectoryPage(
        'fabric-requirements',
        query,
        readRequirementPage,
        signal,
    );
export const requestModelDetail = async (
    modelId: number,
    signal: AbortSignal,
) => {
    const model = readModelDetail(
        await requestReadJson<unknown>(`${root}/models/${modelId}`, {
            signal,
            cache: 'no-store',
        }),
    );
    if (model.id !== modelId) throw new Error('Сервер вернул другую модель. Повторите загрузку.');
    return model;
};
export const requestReferenceChoice = async (
    kind: ReferenceKind,
    value: number,
    signal: AbortSignal,
) => {
    const rows = await requestReadJson<ReferenceChoice[]>(
        `${root}/directory/selected?kind=${kind}&ids=${value}`,
        { signal, cache: 'no-store' },
    );
    if (
        !Array.isArray(rows) ||
        rows.length > 1 ||
        rows.some(
            (row) =>
                !isReferenceChoice(row) ||
                row.id !== value ||
                (kind === 'boxes' && !isReferenceId(row.max_items)),
        )
    )
        throw new Error('Не удалось прочитать выбранную запись.');
    return rows[0] ?? null;
};
