'use client';

import type { ReactNode } from 'react';
import { SplashScreen } from '@/components/shared/SplashScreen';
import { useSplashController } from '@/hooks/browser/useSplashController';

export const SplashBoundary = ({ children }: { children: ReactNode }) => {
    const controller = useSplashController();

    return (
        <>
            <SplashScreen controller={controller} />
            {children}
        </>
    );
};
