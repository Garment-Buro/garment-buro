import type { CrmProjectPage, CrmProjectQuery } from '@/lib/crm/types';

import { requestJson } from './http';

const projectQueryString = (query: CrmProjectQuery) => {
    const search = new URLSearchParams();
    if (query.status) search.set('status', query.status);
    if (query.assignedToUserId) {
        search.set('assigned_to_user_id', String(query.assignedToUserId));
    }
    if (query.cursor) search.set('cursor', String(query.cursor));
    search.set('limit', String(query.limit ?? 50));
    return search.toString();
};

export const getCrmProjects = (
    token: string,
    query: CrmProjectQuery = {},
    signal?: AbortSignal,
) => requestJson<CrmProjectPage>(`/crm/projects?${projectQueryString(query)}`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
});
