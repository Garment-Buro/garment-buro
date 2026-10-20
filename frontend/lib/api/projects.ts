import type {
    ProjectCreate,
    ProjectDetail,
    ProjectImage,
    ProjectImages,
    ProjectKind,
    ProjectPage,
    ProjectSummary,
    ProjectUpdate,
} from '../projects/types.ts';
import { bearerHeaders } from './headers.ts';
import { ApiError, request, requestJson } from './http.ts';

function resourceId(id: number) {
    if (!Number.isInteger(id) || id <= 0 || id > 2_147_483_647)
        throw new RangeError('A persisted resource ID is required');
    return id;
}
const jsonHeaders = (token: string) => ({
    ...bearerHeaders(token),
    'Content-Type': 'application/json',
});
const projectPath = (id: number) => `/profile/projects/${resourceId(id)}`;

export const createProject = (payload: ProjectCreate, token: string, signal?: AbortSignal) =>
    requestJson<ProjectDetail>('/profile/projects', {
        method: 'POST',
        headers: jsonHeaders(token),
        body: JSON.stringify(payload),
        cache: 'no-store',
        signal,
    });
export const updateProject = (
    id: number,
    payload: ProjectUpdate,
    token: string,
    signal?: AbortSignal,
) =>
    requestJson<ProjectDetail>(projectPath(id), {
        method: 'PUT',
        headers: jsonHeaders(token),
        body: JSON.stringify(payload),
        cache: 'no-store',
        signal,
    });
export const getProject = (id: number, token: string, signal?: AbortSignal) =>
    requestJson<ProjectDetail>(projectPath(id), {
        headers: bearerHeaders(token),
        cache: 'no-store',
        signal,
    });
export function getProjectByClientKey(key: string, token: string, signal?: AbortSignal) {
    if (!/^[a-zA-Z0-9_-]{1,100}$/.test(key)) throw new RangeError('Invalid project creation key');
    return requestJson<ProjectSummary>(`/profile/projects/by-client-key/${key}`, {
        headers: bearerHeaders(token), cache: 'no-store', signal,
    }).catch(error => {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
    });
}
export const getProjects = (
    kind: ProjectKind,
    token: string,
    page: { limit?: number; cursor?: number | null } = {},
    signal?: AbortSignal,
) => {
    const query = new URLSearchParams({ kind, limit: String(page.limit ?? 24) });
    if (page.cursor != null) query.set('cursor', String(resourceId(page.cursor)));
    return requestJson<ProjectPage>(`/profile/projects?${query}`, {
        headers: bearerHeaders(token),
        cache: 'no-store',
        signal,
    });
};
export const getProjectImages = (
    id: number,
    version: number,
    token: string,
    signal?: AbortSignal,
) =>
    requestJson<ProjectImages>(`${projectPath(id)}/media?version=${resourceId(version)}`, {
        headers: bearerHeaders(token),
        cache: 'no-store',
        signal,
    });
export const uploadProjectImage = (image: Blob, token: string, signal?: AbortSignal) => {
    const body = new FormData();
    body.append('file', image, 'project-image');
    return requestJson<ProjectImage>('/profile/project-media', {
        method: 'POST',
        body,
        headers: bearerHeaders(token),
        cache: 'no-store',
        signal,
    });
};
export async function deleteProject(
    id: number,
    version: number,
    token: string,
    signal?: AbortSignal,
) {
    await request(`${projectPath(id)}?expected_version=${resourceId(version)}`, {
        method: 'DELETE',
        headers: bearerHeaders(token),
        cache: 'no-store',
        signal,
    });
}
