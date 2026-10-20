'use client';

import { useEffect, useState } from 'react';
import { getStorefrontOptions, type StorefrontOptions } from '@/lib/api/storefront';

export function useStorefrontOptions() {
    const [attempt, setAttempt] = useState(0);
    const [state, setState] = useState<{options:StorefrontOptions | null; error:boolean}>({options:null, error:false});
    useEffect(() => {
        const controller = new AbortController();
        getStorefrontOptions(controller.signal).then(options => {
            if(!controller.signal.aborted) setState({options, error:false});
        }).catch(() => {
            if(!controller.signal.aborted) setState({options:null, error:true});
        });
        return () => controller.abort();
    }, [attempt]);
    return {...state, retry:() => {setState({options:null, error:false}); setAttempt(value => value+1)}};
}
