import type {ResourceInitial, ResourcePage} from './pagedResource.ts';

/** Explicit public projection, separate from the authenticated identity. */
export interface PublicPerson {
    id: number;
    slug: string;
    display_name: string;
    bio: string;
    avatar_id: number | null;
}

export interface OwnPublicProfile extends PublicPerson {
    is_published: boolean;
    version: number;
}

export interface PublicProfileWrite {
    slug: string;
    display_name: string;
    bio: string;
    is_published: boolean;
    version: number;
}

export interface PeopleQuery {
    query?: string;
    sort?: 'newest' | 'name';
    limit?: number;
    cursor?: string | null;
}

export type PeoplePage = ResourcePage<PublicPerson, string>;
export type PeopleInitial = ResourceInitial<PublicPerson, string>;

export function peopleSearchParams(query: PeopleQuery) {
    const params = new URLSearchParams();
    if (query.query?.trim()) params.set('query', query.query.trim());
    if (query.sort) params.set('sort', query.sort);
    if (query.limit != null) params.set('limit', String(query.limit));
    if (query.cursor) params.set('cursor', query.cursor);
    return params.toString();
}

export const peopleQueryKey = (query: PeopleQuery) => peopleSearchParams({...query, cursor:null});

export function validatePersonSlug(slug: string) {
    if (!/^[a-z0-9][a-z0-9-]{2,63}$/.test(slug)) throw new RangeError('A public profile slug is required');
    return slug;
}

export const personHref = (slug: string) => `/people/${validatePersonSlug(slug)}`;

export function validateProfileResourceId(id: number) {
    if (!Number.isInteger(id) || id <= 0 || id > 2_147_483_647) throw new RangeError('A persisted profile resource ID is required');
    return id;
}

export function validateProfileVersion(version: number, creating = false) {
    if (!Number.isInteger(version) || version < (creating ? 0 : 1) || version > 2_147_483_646) throw new RangeError('A current profile version is required');
    return version;
}

/** Request the revocable API directly; never pass this URL through an image cache. */
export function publicAvatarHref(person: PublicPerson, rendition: 'full' | 'card' = 'full') {
    return person.avatar_id === null ? null : `/api/people/${validatePersonSlug(person.slug)}/avatar/${validateProfileResourceId(person.avatar_id)}${rendition === 'card' ? '/preview' : ''}`;
}
