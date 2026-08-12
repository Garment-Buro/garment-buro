"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import {
    isSplashHiddenRoute,
    PWA_REFRESH_SPLASH_SKIP_KEY,
    SPLASH_APP_RUN_KEY,
    SPLASH_SESSION_KEY,
} from '@/lib/browser/utils/splash';
import { useVideoQueue } from '@/store/videoQueueStore';

type SplashWindow = Window & { [SPLASH_APP_RUN_KEY]?: boolean };

export const useSplashController = () => {
    const pathname = usePathname();
    const isOfferRoute = pathname === '/offer';
    const isHiddenRoute = isSplashHiddenRoute(pathname);
    const [show, setShow] = useState(false);
    const [revealed, setRevealed] = useState(false);
    const [exiting, setExiting] = useState(false);

    const videoRef = useRef<HTMLVideoElement>(null);
    const { registerVideo, unregisterVideo, setVideoStatus } = useVideoQueue();
    const [logoReady, setLogoReady] = useState(false);

    useEffect(() => {
        if (isHiddenRoute) {
            if (isOfferRoute) {
                const splashWindow = window as SplashWindow;
                splashWindow[SPLASH_APP_RUN_KEY] = true;
                sessionStorage.setItem(SPLASH_SESSION_KEY, 'done');
            }
            setVideoStatus('logo', 'loaded');
            return;
        }

        registerVideo('logo', 0);
        const standaloneNavigator = navigator as Navigator & { standalone?: boolean };
        const isStandaloneApp = window.matchMedia('(display-mode: standalone)').matches || standaloneNavigator.standalone === true;
        const splashWindow = window as SplashWindow;
        const skipAfterPullRefresh = sessionStorage.getItem(PWA_REFRESH_SPLASH_SKIP_KEY) === '1';
        const alreadyShown = !isStandaloneApp && sessionStorage.getItem(SPLASH_SESSION_KEY);
        if (skipAfterPullRefresh) {
            sessionStorage.removeItem(PWA_REFRESH_SPLASH_SKIP_KEY);
            setVideoStatus('logo', 'loaded');
            return () => unregisterVideo('logo');
        }
        if (splashWindow[SPLASH_APP_RUN_KEY]) {
            setVideoStatus('logo', 'loaded');
            return () => unregisterVideo('logo');
        }
        if (alreadyShown) {
            setVideoStatus('logo', 'loaded');
            return () => unregisterVideo('logo');
        }
        splashWindow[SPLASH_APP_RUN_KEY] = true;
        sessionStorage.setItem(SPLASH_SESSION_KEY, 'showing');
        const openTimer = window.setTimeout(() => setShow(true), 0);
        return () => {
            window.clearTimeout(openTimer);
            unregisterVideo('logo');
        };
    }, [isHiddenRoute, isOfferRoute, registerVideo, unregisterVideo, setVideoStatus]);

    useEffect(() => {
        if (!show) return;
        document.body.style.overflow = 'hidden';
        const videoQueueFallbackTimer = window.setTimeout(() => {
            setVideoStatus('logo', 'loaded');
        }, 1600);

        return () => {
            window.clearTimeout(videoQueueFallbackTimer);
            document.body.style.overflow = '';
        };
    }, [setVideoStatus, show]);

    const dismiss = () => {
        if (exiting) return;
        setExiting(true);
        sessionStorage.setItem(SPLASH_SESSION_KEY, 'done');
        window.dispatchEvent(new Event('p2o_splash_done'));
        setTimeout(() => {
            setShow(false);
            document.body.style.overflow = '';
        }, 650);
    };

    const tryPlayLogo = useCallback(() => {
        const video = videoRef.current;
        if (!video) return;
        video.muted = true;
        video.defaultMuted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('muted', '');
        video.setAttribute('autoplay', '');
        video.setAttribute('playsinline', '');
        video.setAttribute('webkit-playsinline', '');
        video.removeAttribute('controls');
        const maybePromise = video.play();
        if (maybePromise && typeof maybePromise.catch === 'function') {
            maybePromise.catch(() => { });
        }
    }, []);

    const handleLogoPlaying = () => {
        if (!logoReady) {
            setLogoReady(true);
            setRevealed(true);
            setVideoStatus('logo', 'loaded');
        }
    };

    const handleLogoError = () => {
        setLogoReady(false);
        setRevealed(false);
        setVideoStatus('logo', 'loaded');
    };

    useEffect(() => {
        if (!show) return;
        const retryTimers = [0, 180, 600].map((delay) => window.setTimeout(tryPlayLogo, delay));
        const resumePlayback = () => tryPlayLogo();
        const handleVisibilityChange = () => {
            if (!document.hidden) resumePlayback();
        };

        window.addEventListener('pageshow', resumePlayback);
        document.addEventListener('visibilitychange', handleVisibilityChange);

        return () => {
            retryTimers.forEach((timer) => window.clearTimeout(timer));
            window.removeEventListener('pageshow', resumePlayback);
            document.removeEventListener('visibilitychange', handleVisibilityChange);
        };
    }, [show, tryPlayLogo]);

    return {
        isHiddenRoute,
        show,
        revealed,
        exiting,
        videoRef,
        logoReady,
        dismiss,
        tryPlayLogo,
        handleLogoPlaying,
        handleLogoError,
    };
};

export type SplashController = ReturnType<typeof useSplashController>;
