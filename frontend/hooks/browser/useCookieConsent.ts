"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';

import { isCookieConsentHiddenRoute } from '@/lib/browser/utils/cookieConsent';

const COOKIE_CONSENT_FADE_OUT_MS = 360;

export const useCookieConsent = () => {
    const pathname = usePathname();
    const [isMounted, setIsMounted] = useState(false);
    const [isVisible, setIsVisible] = useState(false);
    const openFrameRef = useRef<number | null>(null);
    const closeTimerRef = useRef<number | null>(null);
    const isHiddenRoute = isCookieConsentHiddenRoute(pathname);

    const cancelOpenFrame = useCallback(() => {
        if (openFrameRef.current === null) return;
        window.cancelAnimationFrame(openFrameRef.current);
        openFrameRef.current = null;
    }, []);

    const showBanner = useCallback(() => {
        if (closeTimerRef.current !== null) {
            window.clearTimeout(closeTimerRef.current);
            closeTimerRef.current = null;
        }
        cancelOpenFrame();
        setIsMounted(true);
        openFrameRef.current = window.requestAnimationFrame(() => {
            openFrameRef.current = window.requestAnimationFrame(() => {
                setIsVisible(true);
                openFrameRef.current = null;
            });
        });
    }, [cancelOpenFrame]);

    const hideBanner = useCallback(() => {
        cancelOpenFrame();
        setIsVisible(false);
        if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current);
        closeTimerRef.current = window.setTimeout(() => {
            setIsMounted(false);
            closeTimerRef.current = null;
        }, COOKIE_CONSENT_FADE_OUT_MS);
    }, [cancelOpenFrame]);

    useEffect(() => {
        let actionTimer: number | null = null;
        const clearActionTimer = () => {
            if (actionTimer !== null) window.clearTimeout(actionTimer);
        };
        if (isHiddenRoute || localStorage.getItem('cookieConsent')) {
            actionTimer = window.setTimeout(hideBanner, 0);
            return clearActionTimer;
        }

        const splashState = sessionStorage.getItem('p2o_splash_session');
        const onDone = () => showBanner();
        if (!splashState || splashState === 'done') {
            actionTimer = window.setTimeout(showBanner, 0);
        } else {
            window.addEventListener('p2o_splash_done', onDone, { once: true });
        }

        return () => {
            window.removeEventListener('p2o_splash_done', onDone);
            clearActionTimer();
        };
    }, [hideBanner, isHiddenRoute, showBanner]);

    useEffect(() => () => {
        cancelOpenFrame();
        if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current);
    }, [cancelOpenFrame]);

    const accept = useCallback(() => {
        localStorage.setItem('cookieConsent', 'true');
        hideBanner();
    }, [hideBanner]);

    return { isHiddenRoute, isMounted, isVisible, accept };
};
