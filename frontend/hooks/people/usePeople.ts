'use client';

import {getPeople} from '@/lib/api/people';
import {peopleQueryKey, type PeopleInitial, type PeopleQuery} from '@/lib/catalog/people';
import {usePublicCatalog} from '@/hooks/catalog/usePublicCatalog';

export function usePeople(query: PeopleQuery, active = true, initial?: PeopleInitial) {
    return usePublicCatalog(query, peopleQueryKey(query), getPeople, active, initial);
}
