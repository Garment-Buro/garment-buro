"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { useCatalogVideoAutoplay } from '@/store/catalogVideoAutoplayStore';
import { useCanLoadVideo, useVideoQueue } from '@/store/videoQueueStore';
import { useVideoFrameReveal } from '@/hooks/media/useVideoFrameReveal';

type DesktopCatalogCardVideoOptions = {
    productId: number;
    priority: number;
    videoSrc?: string;
};

export const useDesktopCatalogCardVideo = ({
    productId,
    priority,
    videoSrc,
}: DesktopCatalogCardVideoOptions) => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const stallTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const stallRetryRef = useRef(0);
    const [videoReady, setVideoReady] = useState(false);
    const [isHovered, setIsHovered] = useState(false);
    const [isVideoPlaying, setIsVideoPlaying] = useState(false);
    const [hasPlaybackStarted, setHasPlaybackStarted] = useState(false);
    const [shouldLoadNearViewport, setShouldLoadNearViewport] = useState(false);
    const { hasPresentedFrame, hideVideoUntilFirstFrame, revealVideoAfterFirstFrame } = useVideoFrameReveal(videoRef);
    const queueId = `desktop-card-${priority}-${productId}`;
    const { registerVideo, unregisterVideo, setVideoStatus } = useVideoQueue();
    const canLoadQueue = useCanLoadVideo(queueId);
    const isCatalogVideoActive = useCatalogVideoAutoplay(queueId, containerRef, Boolean(videoSrc));

    useEffect(() => {
        if (!videoSrc || !containerRef.current) return;
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting) {
                setShouldLoadNearViewport(true);
                observer.disconnect();
            }
        }, { threshold: 0.01, rootMargin: '500px 0px' });
        observer.observe(containerRef.current);
        return () => observer.disconnect();
    }, [videoSrc]);

    useEffect(() => {
        if (!videoSrc || !shouldLoadNearViewport) return;
        registerVideo(queueId, priority);
        const video = videoRef.current;
        return () => {
            if (stallTimerRef.current) clearTimeout(stallTimerRef.current);
            unregisterVideo(queueId);
            video?.pause();
        };
    }, [priority, queueId, registerVideo, shouldLoadNearViewport, unregisterVideo, videoSrc]);

    const playFromCurrentPosition = useCallback(() => {
        const video = videoRef.current;
        if (!video || document.hidden) return;
        if (video.ended || (Number.isFinite(video.duration) && video.currentTime >= video.duration - 0.05)) {
            video.currentTime = 0;
        }
        video.play().catch(() => undefined);
    }, []);

    useEffect(() => {
        if (isHovered && videoReady) playFromCurrentPosition();
    }, [isHovered, playFromCurrentPosition, videoReady]);

    useEffect(() => {
        if (isCatalogVideoActive && videoReady) playFromCurrentPosition();
    }, [isCatalogVideoActive, playFromCurrentPosition, videoReady]);

    useEffect(() => {
        if (!videoSrc || !isCatalogVideoActive || !videoReady) return;
        const handleVisibilityChange = () => {
            if (!document.hidden) playFromCurrentPosition();
        };
        window.addEventListener('p2o_splash_done', playFromCurrentPosition);
        window.addEventListener('pageshow', playFromCurrentPosition);
        window.addEventListener('focus', playFromCurrentPosition);
        document.addEventListener('visibilitychange', handleVisibilityChange);
        return () => {
            window.removeEventListener('p2o_splash_done', playFromCurrentPosition);
            window.removeEventListener('pageshow', playFromCurrentPosition);
            window.removeEventListener('focus', playFromCurrentPosition);
            document.removeEventListener('visibilitychange', handleVisibilityChange);
        };
    }, [isCatalogVideoActive, playFromCurrentPosition, videoReady, videoSrc]);

    useEffect(() => {
        if (!isCatalogVideoActive && !isHovered) videoRef.current?.pause();
    }, [isCatalogVideoActive, isHovered]);

    const markVideoReady = () => {
        stallRetryRef.current = 0;
        if (videoSrc) setVideoStatus(queueId, 'loaded');
        setVideoReady(true);
    };

    const handleProgress = () => {
        const video = videoRef.current;
        if (!video) return;
        if (video.readyState >= 4) {
            markVideoReady();
            return;
        }
        if (video.duration > 0 && video.buffered.length > 0) {
            const bufferedEnd = video.buffered.end(video.buffered.length - 1);
            if (Math.round((bufferedEnd / video.duration) * 100) >= 95) markVideoReady();
        }
    };

    const handlePlaybackInterruption = () => {
        const video = videoRef.current;
        if (!video) return;
        setIsVideoPlaying(false);
        hideVideoUntilFirstFrame();
        const started = video.currentTime > 0.05 && !video.ended;
        if (!(isCatalogVideoActive || isHovered || hasPlaybackStarted || started)) return;
        video.play().catch(() => undefined);
        if (stallTimerRef.current) clearTimeout(stallTimerRef.current);
        stallTimerRef.current = setTimeout(() => {
            const current = videoRef.current;
            if (!current || current.ended || current.readyState >= 3) return;
            stallRetryRef.current += 1;
            if (stallRetryRef.current <= 2) {
                const resumeTime = current.currentTime;
                current.load();
                current.addEventListener('loadedmetadata', () => {
                    if (!videoRef.current) return;
                    try { videoRef.current.currentTime = resumeTime; } catch { /* recovery seek is best effort */ }
                    videoRef.current.play().catch(() => undefined);
                }, { once: true });
                return;
            }
            setIsVideoPlaying(false);
            setHasPlaybackStarted(false);
            if (videoSrc) setVideoStatus(queueId, 'error');
        }, 1200);
    };

    const shouldLoad = canLoadQueue && shouldLoadNearViewport;

    useEffect(() => {
        if (shouldLoad && !videoReady && videoSrc) setVideoStatus(queueId, 'loading');
    }, [queueId, setVideoStatus, shouldLoad, videoReady, videoSrc]);

    return {
        videoRef,
        containerRef,
        shouldLoad,
        showVideo: Boolean(videoSrc && isVideoPlaying && hasPlaybackStarted && hasPresentedFrame),
        handleMouseEnter: () => setIsHovered(true),
        handleMouseLeave: () => setIsHovered(false),
        handleCanPlayThrough: markVideoReady,
        handleProgress,
        handlePlaybackInterruption,
        handlePlaying: () => {
            stallRetryRef.current = 0;
            setIsVideoPlaying(true);
            setHasPlaybackStarted(true);
            revealVideoAfterFirstFrame();
        },
        handleEnded: () => {
            setIsVideoPlaying(false);
            setHasPlaybackStarted(false);
            hideVideoUntilFirstFrame();
        },
        handlePause: () => {
            const video = videoRef.current;
            setIsVideoPlaying(false);
            hideVideoUntilFirstFrame();
            if (video && hasPlaybackStarted && !video.ended && (isCatalogVideoActive || isHovered)) {
                video.play().catch(() => undefined);
            }
        },
        handleError: () => {
            if (stallTimerRef.current) clearTimeout(stallTimerRef.current);
            setIsVideoPlaying(false);
            setHasPlaybackStarted(false);
            hideVideoUntilFirstFrame();
            if (videoSrc) setVideoStatus(queueId, 'error');
        },
    };
};
