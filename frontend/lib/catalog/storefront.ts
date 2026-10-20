import {boundedProductIds} from '../products/identity.ts';
import type {ResourceInitial} from './pagedResource.ts';

export type StorefrontSource = 'garment_buro' | 'user';
export type StorefrontSort = 'newest' | 'oldest' | 'cheap' | 'expensive';

export interface StorefrontProduct {
    id: number;
    title: string;
    /** Decimal string from PostgreSQL; never use floating point for checkout totals. */
    price: string;
    category_id: number | null;
    category_name: string | null;
    colors: string[];
    tags: string[];
    source: StorefrontSource;
    image_url: string | null;
    image_alt: string | null;
}

export interface StorefrontPage {
    items: StorefrontProduct[];
    next_cursor: string | null;
}

export type StorefrontInitial = ResourceInitial<StorefrontProduct, string>;

export interface StorefrontOptions {
    categories: {id: number; name: string}[];
    colors: string[];
}

export interface StorefrontQuery {
    query?: string;
    categoryIds?: readonly number[];
    colors?: readonly string[];
    source?: StorefrontSource | null;
    minPrice?: number | null;
    maxPrice?: number | null;
    sort?: StorefrontSort;
    ids?: readonly number[];
    limit?: number;
    cursor?: string | null;
}

export function storefrontSearchParams(query: StorefrontQuery): string {
    const params = new URLSearchParams();
    if(query.query?.trim()) params.set('query', query.query.trim());
    for(const id of query.categoryIds ?? []) params.append('category_ids', String(id));
    for(const color of query.colors ?? []) params.append('colors', color);
    for(const id of boundedProductIds(query.ids ?? [])) params.append('ids', String(id));
    if(query.source) params.set('source', query.source);
    if(query.minPrice != null) params.set('min_price', String(query.minPrice));
    if(query.maxPrice != null) params.set('max_price', String(query.maxPrice));
    if(query.sort) params.set('sort', query.sort);
    if(query.limit != null) params.set('limit', String(query.limit));
    if(query.cursor) params.set('cursor', query.cursor);
    return params.toString();
}

/** A list's identity is its filters; subsequent pages keep the same identity. */
export const storefrontQueryKey = (query: StorefrontQuery) => storefrontSearchParams({...query, cursor:null});
