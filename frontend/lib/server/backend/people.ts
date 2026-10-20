import 'server-only';
import {peopleQueryKey, validatePersonSlug, type PeopleInitial, type PeoplePage, type PeopleQuery, type PublicPerson} from '../../catalog/people.ts';
import {serverFetch, serverRequestJson} from './http.ts';

export async function getInitialPeople(query: PeopleQuery): Promise<PeopleInitial> {
    const key = peopleQueryKey(query);
    try {
        const page = await serverRequestJson<PeoplePage>(`/people?${key}`, {
            cache:'no-store', signal:AbortSignal.timeout(2000),
        });
        return {key, page};
    } catch {
        return {key, error:'unavailable'};
    }
}

export async function getPublicPerson(slug: string): Promise<PublicPerson | null> {
    const response = await serverFetch(`/people/${validatePersonSlug(slug)}`, {
        cache:'no-store', signal:AbortSignal.timeout(2000),
    });
    if (response.status === 404) return null;
    if (!response.ok) throw new Error('Public profile is temporarily unavailable');
    return response.json() as Promise<PublicPerson>;
}
