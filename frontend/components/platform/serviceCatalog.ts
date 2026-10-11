export const categories = ['Футболки', 'Толстовки', 'Худи', 'Лонги', 'Майки', 'Аксессуары'] as const;
export const colors = ['Чёрный', 'Белый', 'Серый', 'Зелёный', 'Бордовый'] as const;
export type Category = typeof categories[number];
export type Color = typeof colors[number];
export type Source = 'community' | 'user';
export type Sort = 'expensive' | 'cheap' | 'oldest' | 'newest';
export interface CatalogFilters {
    categories: Category[];
    colors: Color[];
    source: Source | null;
    sort: Sort;
    minPrice: number;
    maxPrice: number;
}
export const defaultFilters: CatalogFilters = {
    categories: [], colors: [], source: null, sort: 'newest', minPrice: 3000, maxPrice: 30000,
};
interface FilterableProduct {
    category: Category; color: Color; source: Source; price: number; createdOrder: number;
}
export function filterCatalog<T extends FilterableProduct>(items: readonly T[], filters: CatalogFilters): T[] {
    const filtered = items.filter(item => (
        (!filters.categories.length || filters.categories.includes(item.category))
        && (!filters.colors.length || filters.colors.includes(item.color))
        && (!filters.source || item.source === filters.source)
        && item.price >= filters.minPrice && item.price <= filters.maxPrice
    ));
    return filtered.sort((a, b) => {
        if (filters.sort === 'expensive') return b.price - a.price || b.createdOrder - a.createdOrder;
        if (filters.sort === 'cheap') return a.price - b.price || b.createdOrder - a.createdOrder;
        return filters.sort === 'oldest' ? a.createdOrder - b.createdOrder : b.createdOrder - a.createdOrder;
    });
}
export function hasActiveFilters(filters: CatalogFilters): boolean {
    return !!(filters.categories.length || filters.colors.length || filters.source
        || filters.sort !== defaultFilters.sort || filters.minPrice !== defaultFilters.minPrice
        || filters.maxPrice !== defaultFilters.maxPrice);
}
