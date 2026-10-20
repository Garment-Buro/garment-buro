"use client";

import { useCallback, useEffect, useMemo, useSyncExternalStore } from "react";
import { getConstructorPrice } from "@/lib/api/storefront";
import {
    ConstructorPriceResource,
    currentPriceQuote,
    priceRequestKey,
    type ConstructorPriceRequest,
} from "@/lib/constructor/priceResource";

export function useConstructorPrice(input: ConstructorPriceRequest | null) {
    const resource = useMemo(() => new ConstructorPriceResource(), []);
    const key = priceRequestKey(input);
    const stableInput = useMemo<ConstructorPriceRequest | null>(() => (key === null ? null : JSON.parse(key)), [key]);
    const snapshot = useSyncExternalStore(resource.subscribe, resource.getSnapshot, resource.getSnapshot);
    useEffect(() => {
        void resource.load(stableInput, getConstructorPrice);
        return () => resource.dispose();
    }, [resource, stableInput]);
    const retry = useCallback(() => {
        void resource.load(stableInput, getConstructorPrice, 0);
    }, [resource, stableInput]);
    return {
        quote: currentPriceQuote(snapshot, stableInput),
        error: snapshot.key === key && snapshot.status === "error" ? snapshot.error : null,
        retry,
    };
}
