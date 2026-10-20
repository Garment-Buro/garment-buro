'use client';

import {useEffect, useState, useSyncExternalStore} from 'react';
import {PagedResource, type ResourceInitial, type ResourcePage} from '@/lib/catalog/pagedResource';

/** One mounted list owns its request, cursor and cancellation lifecycle. */
export function usePagedCatalog<Item extends {id:number | string}, Query extends {query?:string;cursor?:string | null}>(
    query: Query, key: string, load: (query:Query, signal:AbortSignal) => Promise<ResourcePage<Item,string>>,
    active: boolean, initial?: ResourceInitial<Item,string>, reuseSettled = false,
) {
    const [owner, setOwner] = useState(() => ({initial,
        resource:new PagedResource<Item>(initial?.key === key ? initial : undefined),
    }));
    if(owner.initial !== initial) {
        // A router refresh replaces matching server data without erasing another active search.
        setOwner({initial,resource:initial?.key === key ? new PagedResource<Item>(initial) : owner.resource});
    }
    const {resource} = owner;
    const snapshot = useSyncExternalStore(resource.subscribe,resource.getSnapshot,resource.getSnapshot);
    const serialized = JSON.stringify(query);
    useEffect(() => {
        if(!active) {resource.dispose();return}
        const parameters = JSON.parse(serialized) as Query;
        const timer = window.setTimeout(() => {
            void resource.start(key,(cursor,signal) => load({...parameters,cursor},signal),{reuseSettled});
        },parameters.query?.trim() ? 250 : 0);
        return () => {window.clearTimeout(timer);resource.dispose()};
    },[key,serialized,load,active,resource,reuseSettled]);
    const state = snapshot.key === key ? snapshot : {
        key,status:'loading' as const,items:[],nextCursor:null,loadingMore:false,error:null,
    };
    return {...state,loadMore:resource.loadMore,retry:resource.reload};
}
