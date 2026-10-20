export type CatalogAdminSort = `${'id' | 'title' | 'price' | 'stock' | 'variants'}:${'asc' | 'desc'}`;
export type CatalogAdminQuery = {
    query?: string;
    garment_model_id?: number;
    category_id?: number;
    community_id?: number;
    active?: boolean;
    source?: 'all' | 'garment_buro' | 'user';
    stock?: 'all' | 'available' | 'empty';
    sort?: CatalogAdminSort;
    limit?: number;
    cursor?: string | null;
};
export interface CatalogAdminProduct {
    id: number;
    title: string;
    slug: string | null;
    category_id: number | null;
    garment_model_id: number | null;
    preset_source: 'garment_buro' | 'user';
    tags: string[];
    category_name: string | null;
    garment_model_name: string | null;
    price: string;
    old_price: string | null;
    image_url: string | null;
    is_active: boolean;
    stock_quantity: number;
    variant_count: number;
    sku: string | null;
    community_count: number | null;
    communities: Array<{id:number; title:string; slug:string}>;
}
export interface CatalogAdminPage { items: CatalogAdminProduct[]; next_cursor: string | null }
export interface CatalogAdminCounts { garment_buro: number; user: number; communities: number | null }

export function catalogAdminSearch(query: CatalogAdminQuery): string {
    const params = new URLSearchParams();
    for (const [name, value] of Object.entries(query)) {
        if (value !== undefined && value !== null && value !== '') params.set(name, String(value));
    }
    params.sort();
    return params.toString();
}

const nullableText = (value: unknown) => value === null || typeof value === 'string';
const nullableId = (value: unknown) => value === null || (Number.isSafeInteger(value) && Number(value) > 0);
const money = (value: unknown) => typeof value === 'string' && /^\d+(?:\.\d{1,2})?$/.test(value) && Number.isFinite(Number(value));

export function readCatalogAdminPage(value: unknown): CatalogAdminPage {
    const page = value as CatalogAdminPage | null;
    if (!page || !Array.isArray(page.items) || page.items.length > 100
        || !(page.next_cursor === null || (typeof page.next_cursor === 'string' && page.next_cursor.length > 0 && page.next_cursor.length <= 2048))) {
        throw new Error('Сервер вернул неверную страницу моделей.');
    }
    const ids = new Set<number>();
    for (const item of page.items) {
        if (!item || !Number.isSafeInteger(item.id) || item.id <= 0 || ids.has(item.id)
            || typeof item.title !== 'string' || !money(item.price)
            || !(item.old_price === null || money(item.old_price)) || typeof item.is_active !== 'boolean'
            || !nullableId(item.category_id) || !nullableId(item.garment_model_id)
            || !nullableText(item.slug) || !nullableText(item.image_url)
            || !nullableText(item.category_name) || !nullableText(item.garment_model_name)
            || !Number.isSafeInteger(item.stock_quantity) || item.stock_quantity < 0
            || !Number.isSafeInteger(item.variant_count) || item.variant_count < 0 || !nullableText(item.sku)
            || !(item.community_count === null || Number.isSafeInteger(item.community_count) && item.community_count >= 0)
            || !Array.isArray(item.communities) || item.communities.length !== Math.min(3,item.community_count ?? 0)
            || !Array.isArray(item.tags) || !item.tags.every(tag => typeof tag === 'string')
            || !['garment_buro', 'user'].includes(item.preset_source)) {
            throw new Error('Сервер вернул неверную модель.');
        }
        const communities = new Set<number>();
        for (const community of item.communities) {
            if (!community || !Number.isSafeInteger(community.id) || community.id <= 0
                || communities.has(community.id) || typeof community.title !== 'string' || typeof community.slug !== 'string') {
                throw new Error('Сервер вернул неверную связь с лендингом.');
            }
            communities.add(community.id);
        }
        ids.add(item.id);
    }
    return page;
}
