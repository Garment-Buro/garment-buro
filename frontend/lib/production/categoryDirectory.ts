import type { ProductCategory, GarmentModelCategory } from './assortmentTypes.ts';
import { isReferenceChoice, isReferenceCount, isReferenceId, readReferencePage, requestDirectoryPage, type DirectoryQuery, } from './referenceDirectory.ts';
export type CategoryKind = 'model-categories' | 'product-categories';
export type CategoryCard = GarmentModelCategory & {
    item_count: number;
};
export const readCategoryPage = (value: unknown) => readReferencePage<CategoryCard>(value, row => isReferenceChoice(row) && isReferenceId(row.version) && isReferenceCount(row.item_count));
export const requestModelCategories = (query: DirectoryQuery, signal: AbortSignal) => requestDirectoryPage('categories/model-categories', query, readCategoryPage, signal);
export const requestProductCategories = (query: DirectoryQuery, signal: AbortSignal) => requestDirectoryPage('categories/product-categories', query, readCategoryPage, signal);
export function readModelCategory(value: unknown): GarmentModelCategory {
    const row = value as GarmentModelCategory;
    if (!isReferenceChoice(row) || !isReferenceId(row.version))
        throw new Error('Сервер вернул неполную категорию модели.');
    return row;
}
export function readProductCategory(value: unknown): ProductCategory {
    const row = value as ProductCategory;
    if (!row || !isReferenceId(row.id) || !isReferenceId(row.version) || typeof row.name !== 'string' || typeof row.slug !== 'string' || typeof row.is_active !== 'boolean' || !(row.description === null || typeof row.description === 'string'))
        throw new Error('Сервер вернул неполную категорию товара.');
    return row;
}
