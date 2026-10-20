import {peopleSearchParams, validatePersonSlug, validateProfileResourceId, validateProfileVersion, type OwnPublicProfile, type PeoplePage, type PeopleQuery, type PublicProfileWrite} from '../catalog/people.ts';
import {bearerHeaders} from './headers.ts';
import {request, requestJson} from './http.ts';
import {requestPublicPage} from './publicPages.ts';

export const getPeople = (query: PeopleQuery, signal?: AbortSignal) => requestPublicPage<PeoplePage>(
    `/people?${peopleSearchParams(query)}`, {signal, cache:'no-store'},
);

export const getOwnPublicProfile = (token: string, signal?: AbortSignal) => requestJson<OwnPublicProfile | null>(
    '/profile/public', {headers:bearerHeaders(token), signal, cache:'no-store'},
);

export async function savePublicProfile(token: string, profile: PublicProfileWrite, signal?: AbortSignal) {
    const {slug, display_name, bio, is_published, version} = profile;
    validatePersonSlug(slug);
    validateProfileVersion(version, true);
    return requestJson<OwnPublicProfile>('/profile/public', {
        method:'PUT', headers:{...bearerHeaders(token), 'Content-Type':'application/json'},
        signal, cache:'no-store', body:JSON.stringify({slug, display_name, bio, is_published, version}),
    });
}

export async function uploadProfileAvatar(token: string, version: number, file: Blob, signal?: AbortSignal) {
    validateProfileVersion(version);
    if (!file.size || file.size > 8 * 1024 * 1024 || (file.type && !['image/jpeg','image/png','image/webp'].includes(file.type))) {
        throw new RangeError('Выберите JPEG, PNG или WebP до 8 МБ.');
    }
    const body = new FormData();
    body.set('file', file, file instanceof File ? file.name : 'avatar');
    return requestJson<OwnPublicProfile>(`/profile/public/avatar?expected_version=${version}`, {
        method:'POST', headers:bearerHeaders(token), body, signal, cache:'no-store',
    });
}

export async function removeProfileAvatar(token: string, version: number, signal?: AbortSignal) {
    validateProfileVersion(version);
    return requestJson<OwnPublicProfile>(`/profile/public/avatar?expected_version=${version}`, {
        method:'DELETE', headers:bearerHeaders(token), signal, cache:'no-store',
    });
}

export async function readOwnProfileAvatar(token: string, mediaId: number, signal?: AbortSignal) {
    const response = await request(`/profile/public/avatar/${validateProfileResourceId(mediaId)}`, {
        headers:bearerHeaders(token), signal, cache:'no-store',
    });
    const blob = await response.blob();
    signal?.throwIfAborted();
    if (blob.type !== 'image/webp' || !blob.size || blob.size > 2 * 1024 * 1024) throw new Error('Фото временно недоступно.');
    return blob;
}
