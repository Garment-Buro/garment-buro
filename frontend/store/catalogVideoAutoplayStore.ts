"use client";

import { useEffect, useState } from 'react';
import type { RefObject } from 'react';

const CATALOG_VIDEO_DWELL_MS = 2000;
const CATALOG_VIDEO_TOP_BAND_RATIO = 0.55;
const CATALOG_VIDEO_MIN_VISIBLE_PX = 24;

type CatalogVideoCandidate = {
    id: string;
    top: number;
    bottom: number;
    visibleHeight: number;
};

const candidates = new Map<string, CatalogVideoCandidate>();
const subscribers = new Set<() => void>();

let activeVideoId: string | null = null;
let pendingVideoId: string | null = null;
let dwellTimer: ReturnType<typeof setTimeout> | null = null;

const notifySubscribers = () => {
    subscribers.forEach((subscriber) => subscriber());
};

const clearDwellTimer = () => {
    if (!dwellTimer) return;
    clearTimeout(dwellTimer);
    dwellTimer = null;
};

const pickUpperCatalogCandidate = () => {
    if (typeof window === 'undefined') return null;

    const upperBandBottom = window.innerHeight * CATALOG_VIDEO_TOP_BAND_RATIO;
    const visibleCandidates = Array.from(candidates.values())
        .filter((candidate) => {
            return candidate.visibleHeight >= CATALOG_VIDEO_MIN_VISIBLE_PX
                && candidate.bottom > 0
                && candidate.top < upperBandBottom;
        })
        .sort((a, b) => {
            const topDelta = Math.max(0, a.top) - Math.max(0, b.top);
            if (topDelta !== 0) return topDelta;
            return b.visibleHeight - a.visibleHeight;
        });

    return visibleCandidates[0]?.id ?? null;
};

const scheduleActiveCandidate = (candidateId: string | null) => {
    if (candidateId === pendingVideoId) return;

    clearDwellTimer();
    pendingVideoId = candidateId;
    activeVideoId = null;
    notifySubscribers();

    if (!candidateId) return;

    dwellTimer = setTimeout(() => {
        if (pendingVideoId !== candidateId) return;
        activeVideoId = candidateId;
        notifySubscribers();
    }, CATALOG_VIDEO_DWELL_MS);
};

const updateCandidate = (id: string, element: HTMLElement) => {
    if (typeof window === 'undefined') return;

    const rect = element.getBoundingClientRect();
    const visibleTop = Math.max(0, rect.top);
    const visibleBottom = Math.min(window.innerHeight, rect.bottom);
    const visibleHeight = Math.max(0, visibleBottom - visibleTop);

    if (visibleHeight < CATALOG_VIDEO_MIN_VISIBLE_PX || rect.bottom <= 0 || rect.top >= window.innerHeight) {
        candidates.delete(id);
    } else {
        candidates.set(id, {
            id,
            top: rect.top,
            bottom: rect.bottom,
            visibleHeight,
        });
    }

    scheduleActiveCandidate(pickUpperCatalogCandidate());
};

const removeCandidate = (id: string) => {
    candidates.delete(id);
    scheduleActiveCandidate(pickUpperCatalogCandidate());
};

export function useCatalogVideoAutoplay<T extends HTMLElement>(
    id: string,
    elementRef: RefObject<T | null>,
    enabled: boolean
) {
    const [currentActiveVideoId, setCurrentActiveVideoId] = useState(activeVideoId);

    useEffect(() => {
        const subscriber = () => setCurrentActiveVideoId(activeVideoId);
        subscribers.add(subscriber);
        return () => {
            subscribers.delete(subscriber);
        };
    }, []);

    useEffect(() => {
        if (!enabled) {
            removeCandidate(id);
            return undefined;
        }

        let frameId: number | null = null;

        const measure = () => {
            if (frameId !== null) return;
            frameId = window.requestAnimationFrame(() => {
                frameId = null;
                const element = elementRef.current;
                if (!element) {
                    removeCandidate(id);
                    return;
                }
                updateCandidate(id, element);
            });
        };

        measure();
        window.addEventListener('scroll', measure, { passive: true });
        window.addEventListener('resize', measure);

        return () => {
            if (frameId !== null) {
                window.cancelAnimationFrame(frameId);
            }
            window.removeEventListener('scroll', measure);
            window.removeEventListener('resize', measure);
            removeCandidate(id);
        };
    }, [enabled, elementRef, id]);

    return currentActiveVideoId === id;
}
