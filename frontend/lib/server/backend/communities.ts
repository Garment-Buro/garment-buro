import 'server-only';
import {communityQueryKey, type CommunityInitial, type CommunityPage, type CommunityQuery} from '../../catalog/communities.ts';
import {serverRequestJson} from './http.ts';

export async function getInitialCommunities(query: CommunityQuery): Promise<CommunityInitial> {
    const key = communityQueryKey(query);
    try {
        const page = await serverRequestJson<CommunityPage>(`/communities?${key}`, {
            cache:'no-store', signal:AbortSignal.timeout(2000),
        });
        return {key,page};
    } catch {
        return {key,error:'unavailable'};
    }
}
