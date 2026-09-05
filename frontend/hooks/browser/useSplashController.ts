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
import { playSplashVideo } from '@/lib/browser/utils/splashPlayback';

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
    const [playbackIssue, setPlaybackIssue] = useState<'blocked' | 'error' | 'slow' | null>(null);

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

    const handleLogoPlaying = useCallback(() => {
        setLogoReady(true);
        setRevealed(true);
        setPlaybackIssue(null);
        setVideoStatus('logo', 'loaded');
    }, [setVideoStatus]);

    const tryPlayLogo = useCallback(() => {
        const video = videoRef.current;
        if (!video) return;
        void playSplashVideo(video).then((result) => {
            if (videoRef.current !== video) return;
            if (result === 'playing') handleLogoPlaying();
            else if (result !== 'interrupted' && video.paused) {
                setPlaybackIssue(result);
                setRevealed(true);
                setVideoStatus('logo', 'loaded');
            }
        });
    }, [handleLogoPlaying, setVideoStatus]);

    const handleLogoData = () => {
        // A decoded frame is useful even when the browser requires a gesture to play.
        setRevealed(true);
        tryPlayLogo();
    };

    const handleLogoError = () => {
        setLogoReady(false);
        setRevealed(true);
        setPlaybackIssue('error');
        setVideoStatus('logo', 'loaded');
    };

    const retryLogo = () => {
        const video = videoRef.current;
        if (!video) return;
        if (video.error) video.load();
        tryPlayLogo();
    };

    useEffect(() => {
        if (!show || logoReady) return;
        const revealTimer = window.setTimeout(() => {
            setRevealed(true);
            setPlaybackIssue((issue) => issue ?? 'slow');
        }, 3500);
        return () => window.clearTimeout(revealTimer);
    }, [show, logoReady]);

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
        playbackIssue,
        dismiss,
        retryLogo,
        tryPlayLogo,
        handleLogoData,
        handleLogoPlaying,
        handleLogoError,
    };
};

export type SplashController = ReturnType<typeof useSplashController>;
