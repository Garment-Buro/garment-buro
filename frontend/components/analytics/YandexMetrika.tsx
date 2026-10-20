'use client';

import { useEffect, useRef } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';

import { createPublicAnalyticsFrame } from '@/lib/analytics/publicAnalyticsFrame';

export function YandexMetrika() {
    const pathname = usePathname();
    const query = useSearchParams().toString();
    const tracker = useRef<ReturnType<typeof createPublicAnalyticsFrame> | null>(null);

    useEffect(() => {
        const active = createPublicAnalyticsFrame(window, document);
        tracker.current = active;
        active.update();
        return () => { active.dispose(); tracker.current = null; };
    }, []);

    useEffect(() => { tracker.current?.update(); }, [pathname, query]);

    return null;
}
