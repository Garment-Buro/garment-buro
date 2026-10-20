'use client';

import {useEffect, useState, useSyncExternalStore} from 'react';
import {getCommunityFavoriteStatus,getSavedCommunities,setCommunityFavorite} from '@/lib/api/communities';
import type {Community} from '@/lib/catalog/communities';
import {PagedResource} from '@/lib/catalog/pagedResource';
import {runForCustomer,useCustomerAccount} from './customerSession';
import {useCustomerFavoriteMembership} from './useCustomerFavoriteMembership';

const api={status:getCommunityFavoriteStatus,save:setCommunityFavorite};
export const useCommunityFavorites = (ids:readonly number[]) => useCustomerFavoriteMembership(ids,api);

export function useSavedCommunities(active:boolean) {
    const {key:account,userId}=useCustomerAccount();
    const key=`community-favorites:${account ?? 'guest'}`;
    const [resource]=useState(()=>new PagedResource<Community,number>());
    const snapshot=useSyncExternalStore(resource.subscribe,resource.getSnapshot,resource.getSnapshot);
    useEffect(()=>{
        if(!active || userId===null) {resource.dispose();return}
        void resource.start(key,(cursor,signal)=>runForCustomer(userId,
            token=>getSavedCommunities(token,{limit:24,cursor},signal),account));
        return resource.dispose;
    },[active,key,userId,account,resource]);
    const state=snapshot.key===key ? snapshot : {
        key,status:'loading' as const,items:[],nextCursor:null,loadingMore:false,error:null,
    };
    return {...state,authenticated:userId!==null,loadMore:resource.loadMore,retry:resource.reload};
}
