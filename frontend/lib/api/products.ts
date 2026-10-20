import type {CatalogAdminQuery} from '../products/adminCatalog.ts';
import {requestCatalogAdminPage} from './catalogAdmin.ts';
import {bearerHeaders} from './headers';

export const getAdminProducts = (query: CatalogAdminQuery, token: string, signal?: AbortSignal) =>
    requestCatalogAdminPage('/products', query, { signal, headers: bearerHeaders(token) });
