'use client';

import {getCommunities} from '@/lib/api/communities';
import {communityQueryKey, type CommunityInitial, type CommunityQuery} from '@/lib/catalog/communities';
import {usePublicCatalog} from './usePublicCatalog';

export function useCommunities(query:CommunityQuery, active=true, initial?:CommunityInitial) {
    return usePublicCatalog(query,communityQueryKey(query),getCommunities,active,initial);
}
