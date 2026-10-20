'use client';

import { useEffect, useState } from 'react';
import { CART_ACTION_EXPAND_MS, CART_ACTION_REVEAL_MS } from '@/lib/cart/constants';

/** Load on opening; retain the outgoing content until its closing motion ends. */
export function useCartDeferredContent(active: boolean) {
    const [previousActive, setPreviousActive] = useState(active);
    const [exiting, setExiting] = useState(false);
    if (active !== previousActive) {
        setPreviousActive(active);
        setExiting(!active);
    }
    useEffect(() => {
        if (active || !exiting) return;
        const timer = window.setTimeout(() => setExiting(false), Math.max(CART_ACTION_EXPAND_MS, CART_ACTION_REVEAL_MS));
        return () => window.clearTimeout(timer);
    }, [active, exiting]);
    return active || exiting;
}
