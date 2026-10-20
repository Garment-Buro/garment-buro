'use client';

import { useEffect, useState } from 'react';
import { requestReferenceChoice, type ReferenceChoice, type ReferenceKind } from '@/lib/production/referenceDirectory';
import { useProductionAuthStore } from '@/store/productionAuthStore';

/** A selected ID has its own lifetime; result pages never own or clear it. */
export function useSelectedReference(kind: ReferenceKind, value: number, refreshKey = 0) {
    const epoch = useProductionAuthStore(state => state.sessionEpoch);
    const key = `${epoch}:${kind}:${value}:${refreshKey}`;
    const [result, setResult] = useState<{ key: string; row: ReferenceChoice | null; error: string } | null>(null);
    const [revision, setRevision] = useState(0);
    useEffect(() => {
        if (!value || !epoch) return;
        const controller = new AbortController();
        void useProductionAuthStore.getState().runAuthenticated(() => requestReferenceChoice(kind, value, controller.signal))
            .then(row => {
                if (!controller.signal.aborted) setResult({key,row,error:row?'':'Выбранная запись больше не существует.'});
            })
            .catch(error => {
                if (!controller.signal.aborted) setResult({key,row:null,error:error instanceof Error?error.message:'Не удалось прочитать выбранную запись.'});
            });
        return () => controller.abort();
    }, [kind,value,epoch,key,revision]);
    const current = value && epoch && result?.key === key ? result : null;
    return {row:current?.row??null,error:current?.error??'',retry:()=>setRevision(value=>value+1)};
}
