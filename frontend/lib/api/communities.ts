import {boundedCommunityIds, communitySearchParams, validateCommunityId, type Community, type CommunityPage, type CommunityQuery} from '../catalog/communities.ts';
import type {ResourcePage} from '../catalog/pagedResource.ts';
import {bearerHeaders} from './headers.ts';
import {request, requestJson} from './http.ts';
import {requestPublicPage} from './publicPages.ts';

export const getCommunities = (query: CommunityQuery, signal?: AbortSignal) => (
    requestPublicPage<CommunityPage>(`/communities?${communitySearchParams(query)}`, {signal, cache:'no-store'})
);

export async function getCommunityFavoriteStatus(communityIds: readonly number[], token: string, signal?: AbortSignal) {
    const ids = boundedCommunityIds(communityIds);
    if(!ids.length) return [];
    const params = new URLSearchParams();
    ids.forEach(id => params.append('community_ids', String(id)));
    const response = await requestJson<{community_ids:number[]}>(`/profile/community-favorites/status?${params}`, {
        headers:bearerHeaders(token), signal, cache:'no-store',
    });
    return response.community_ids;
}

export const getSavedCommunities = (token: string, page: {limit?:number; cursor?:number | null} = {}, signal?:AbortSignal) => {
    const params = new URLSearchParams({limit:String(page.limit ?? 24)});
    if(page.cursor != null) params.set('cursor',String(page.cursor));
    return requestJson<ResourcePage<Community, number>>(`/profile/community-favorites?${params}`, {
        headers:bearerHeaders(token), signal, cache:'no-store',
    });
};

export async function setCommunityFavorite(id: number, wanted: boolean, token: string, signal?:AbortSignal) {
    await request(`/profile/community-favorites/${validateCommunityId(id)}`, {
        method:wanted ? 'PUT' : 'DELETE', headers:bearerHeaders(token), signal, cache:'no-store',
    });
}
