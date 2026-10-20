import type { StorefrontQuery, StorefrontSort, StorefrontSource } from '@/lib/api/storefront';

export type Sort = StorefrontSort;
export interface CatalogFilters {
    categories: number[];
    colors: string[];
    source: StorefrontSource | null;
    sort: StorefrontSort;
    minPrice: number;
    maxPrice: number | null;
}
export const defaultFilters: CatalogFilters = {
    categories: [], colors: [], source: null, sort: 'newest', minPrice: 0, maxPrice: null,
};
export function createCatalogQuery(query: string, filters: CatalogFilters): StorefrontQuery {
    return {query, categoryIds:filters.categories, colors:filters.colors, source:filters.source,
        minPrice:filters.minPrice, maxPrice:filters.maxPrice, sort:filters.sort, limit:24};
}
export function hasActiveFilters(filters: CatalogFilters): boolean {
    return !!(filters.categories.length || filters.colors.length || filters.source
        || filters.sort !== defaultFilters.sort || filters.minPrice !== defaultFilters.minPrice
        || filters.maxPrice !== defaultFilters.maxPrice);
}
