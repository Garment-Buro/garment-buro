import type {ResourceInitial, ResourcePage} from './pagedResource.ts';

/** Published landing projection; never contains private identity or full landing content. */
export interface Community {
    id: number;
    slug: string;
    title: string;
    description: string;
    owner_name: string;
    image_url: string | null;
}

export interface CommunityQuery {
    query?: string;
    sort?: 'newest' | 'name';
    limit?: number;
    cursor?: string | null;
}

export type CommunityPage = ResourcePage<Community, string>;
export type CommunityInitial = ResourceInitial<Community, string>;

export function communitySearchParams(query: CommunityQuery) {
    const params = new URLSearchParams();
    if(query.query?.trim()) params.set('query',query.query.trim());
    if(query.sort) params.set('sort',query.sort);
    if(query.limit != null) params.set('limit',String(query.limit));
    if(query.cursor) params.set('cursor',query.cursor);
    return params.toString();
}

export const communityQueryKey = (query: CommunityQuery) => communitySearchParams({...query,cursor:null});

export function communityHref(slug: string) {
    if(!/^[a-z0-9][a-z0-9-]{2,95}$/.test(slug)) throw new RangeError('A published landing slug is required');
    return `/p/${slug}`;
}

export function validateCommunityId(value: number) {
    if(!Number.isInteger(value) || value <= 0 || value > 2_147_483_647) throw new RangeError('A persisted community ID is required');
    return value;
}

export function boundedCommunityIds(ids: readonly number[]) {
    if(ids.length > 100) throw new RangeError('At most 100 community IDs per request');
    return [...new Set(ids.map(validateCommunityId))];
}
