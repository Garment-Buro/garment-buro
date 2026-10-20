'use client';

import { useEffect, useState } from 'react';
import { getCheckoutPaymentOptions } from '@/lib/api/checkout';

export function useCheckoutPaymentOptions(active: boolean) {
    const [qrAvailable, setQrAvailable] = useState(false);
    useEffect(() => {
        if (!active) return;
        const abort = new AbortController();
        void getCheckoutPaymentOptions(abort.signal)
            .then(methods => { if (!abort.signal.aborted) setQrAvailable(methods.includes('qr')); })
            .catch(() => { if (!abort.signal.aborted) setQrAvailable(false); });
        return () => abort.abort();
    }, [active]);
    return active && qrAvailable;
}
