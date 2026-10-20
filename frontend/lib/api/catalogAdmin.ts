import { PageCursorExpiredError } from '../catalog/pagedResource.ts';
import { catalogAdminSearch, readCatalogAdminPage, type CatalogAdminQuery } from '../products/adminCatalog.ts';
import { ApiError, requestReadJson } from './http.ts';

export async function requestCatalogAdminPage(path: string, query: CatalogAdminQuery, init?: RequestInit) {
    try {
        return readCatalogAdminPage(await requestReadJson<unknown>(`${path}?${catalogAdminSearch(query)}`, {
            ...init, cache: 'no-store',
        }));
    } catch (error) {
        if (error instanceof ApiError && error.status === 422 && error.code === 'invalid_cursor') {
            throw new PageCursorExpiredError();
        }
        throw error;
    }
}
