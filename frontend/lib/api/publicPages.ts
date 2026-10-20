import {PageCursorExpiredError} from '../catalog/pagedResource.ts';
import {ApiError, requestPublicJson} from './http.ts';

/** Translate the public-list protocol at the API boundary, not inside UI state. */
export async function requestPublicPage<Page>(path: string, init?: RequestInit): Promise<Page> {
    try {
        return await requestPublicJson<Page>(path, init);
    } catch (error) {
        if (error instanceof ApiError && error.status === 422 && error.code === 'invalid_cursor') {
            throw new PageCursorExpiredError();
        }
        throw error;
    }
}
