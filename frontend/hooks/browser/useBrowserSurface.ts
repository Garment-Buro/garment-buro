'use client';

import { useSyncExternalStore } from 'react';

import type { BrowserSurface } from '@/lib/browser/types';
import { detectBrowserSurface } from '@/lib/browser/utils/detectBrowserSurface';

const getServerSnapshot = (): BrowserSurface => 'otherbrowser';

const subscribe = (onStoreChange: () => void) => {
    const displayMode = window.matchMedia('(display-mode: standalone)');
    displayMode.addEventListener('change', onStoreChange);
    return () => displayMode.removeEventListener('change', onStoreChange);
};

export const useBrowserSurface = () => useSyncExternalStore(
    subscribe,
    detectBrowserSurface,
    getServerSnapshot,
);
