'use client';

import {useEffect, useState, useSyncExternalStore} from 'react';
import {emptyFavoriteState, FavoriteController} from '@/lib/catalog/favoriteController';
import {runForCustomer, useCustomerAccount} from './customerSession';

interface CustomerFavoriteApi {
    status:(ids:readonly number[],token:string,signal?:AbortSignal) => Promise<number[]>;
    save:(id:number,wanted:boolean,token:string,signal?:AbortSignal) => Promise<void>;
}

/** The product/community API differs; confirmed state and account lifetime rules are shared. */
export function useCustomerFavoriteMembership(ids:readonly number[], api:CustomerFavoriteApi) {
    const {key,userId,sessionReady}=useCustomerAccount();
    const [controller]=useState(()=>new FavoriteController());
    const snapshot=useSyncExternalStore(controller.subscribe,controller.getSnapshot,controller.getSnapshot);
    const idsKey=JSON.stringify([...new Set(ids)]);
    useEffect(()=>{
        controller.setAccount(key,userId===null ? null : {
            status:(ids,signal)=>runForCustomer(userId,token=>api.status(ids,token,signal),key),
            save:(id,wanted,signal)=>runForCustomer(userId,token=>api.save(id,wanted,token,signal),key),
        });
        return controller.dispose;
    },[key,userId,controller,api]);
    useEffect(()=>{
        if(key) void controller.ensureStatus(JSON.parse(idsKey) as number[]);
    },[key,idsKey,controller]);
    const state=snapshot.account===key ? snapshot : emptyFavoriteState;
    return {...state,authenticated:userId!==null,sessionReady,toggle:controller.toggle,
        retry:()=>controller.refreshStatus(JSON.parse(idsKey) as number[])};
}
