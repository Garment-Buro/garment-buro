"use client";

import { useCallback, useEffect, useRef } from 'react';
import { createPointerSession } from '@/lib/constructor/pointerSession';

/** Browser listeners belong to this mounted editor, including Strict Mode remounts. */
export function useConstructorPointerSession() {
    const session = useRef<ReturnType<typeof createPointerSession> | null>(null);
    useEffect(() => {
        const current = createPointerSession(window, document);
        session.current = current;
        return () => {
            current.dispose();
            session.current = null;
        };
    }, []);
    const start = useCallback((...args: Parameters<ReturnType<typeof createPointerSession>['start']>) => {
        session.current?.start(...args);
    }, []);
    const cancel = useCallback(() => session.current?.cancel(), []);
    return { start, cancel };
}
