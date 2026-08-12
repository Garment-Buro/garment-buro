"use client";

import { useEffect, useRef, useState } from 'react';
import { useCatalogVideoAutoplay } from '@/store/catalogVideoAutoplayStore';
import { useCanLoadVideo, useVideoQueue } from '@/store/videoQueueStore';
import { useVideoFrameReveal } from '@/hooks/media/useVideoFrameReveal';

type MobileCatalogCardVideoOptions = {
    productId: number;
    priority: number;
    videoSrc?: string;
};

export const useMobileCatalogCardVideo = ({
    productId,
    priority,
    videoSrc,
}: MobileCatalogCardVideoOptions) => {
    const [videoReady, setVideoReady] = useState(false);
    const [shouldLoadVideo, setShouldLoadVideo] = useState(false);
    const [progress, setProgress] = useState(0);
    const videoRef = useRef<HTMLVideoElement>(null);
    const containerRef = useRef<HTMLAnchorElement>(null);
    const { hasPresentedFrame, hideVideoUntilFirstFrame, revealVideoAfterFirstFrame } = useVideoFrameReveal(videoRef);
    const queueId = `mobile-card-${priority}-${productId}`;
    const { registerVideo, unregisterVideo, setVideoStatus } = useVideoQueue();
    const canLoadQueue = useCanLoadVideo(queueId);
    const isCatalogVideoActive = useCatalogVideoAutoplay(queueId, containerRef, Boolean(videoSrc));

    const markVideoReady = () => {
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
            const nextProgress = Math.round((bufferedEnd / video.duration) * 100);
            setProgress(nextProgress);
            if (nextProgress >= 95) markVideoReady();
        }
    };

    useEffect(() => {
        if (!videoSrc || !containerRef.current) return;
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting) {
                setShouldLoadVideo(true);
                observer.disconnect();
            }
        }, { threshold: 0.01, rootMargin: '250px 0px' });
        observer.observe(containerRef.current);
        return () => observer.disconnect();
    }, [videoSrc]);

    useEffect(() => {
        if (!videoSrc || !shouldLoadVideo) return;
        registerVideo(queueId, priority);
        const video = videoRef.current;
        return () => {
            unregisterVideo(queueId);
            video?.pause();
        };
    }, [priority, queueId, registerVideo, shouldLoadVideo, unregisterVideo, videoSrc]);

    const actuallyLoadVideo = canLoadQueue && shouldLoadVideo;

    useEffect(() => {
        if (actuallyLoadVideo && !videoReady && videoSrc) setVideoStatus(queueId, 'loading');
    }, [actuallyLoadVideo, queueId, setVideoStatus, videoReady, videoSrc]);

    useEffect(() => {
        if (!actuallyLoadVideo || !videoSrc || !isCatalogVideoActive) return;
        const video = videoRef.current;
        if (!video) return;
        video.muted = true;
        video.playsInline = true;
        const startPlayback = () => {
            const currentVideo = videoRef.current;
            if (!currentVideo || document.hidden) return;
            currentVideo.muted = true;
            currentVideo.playsInline = true;
            currentVideo.play().catch(() => undefined);
        };
        const handleVisibilityChange = () => {
            if (!document.hidden) startPlayback();
        };
        if (video.readyState >= 2) startPlayback();
        else video.addEventListener('loadeddata', startPlayback, { once: true });
        window.addEventListener('p2o_splash_done', startPlayback);
        window.addEventListener('pageshow', startPlayback);
        window.addEventListener('focus', startPlayback);
        document.addEventListener('visibilitychange', handleVisibilityChange);
        return () => {
            video.removeEventListener('loadeddata', startPlayback);
            window.removeEventListener('p2o_splash_done', startPlayback);
            window.removeEventListener('pageshow', startPlayback);
            window.removeEventListener('focus', startPlayback);
            document.removeEventListener('visibilitychange', handleVisibilityChange);
        };
    }, [actuallyLoadVideo, isCatalogVideoActive, videoSrc]);

    useEffect(() => {
        if (!isCatalogVideoActive) videoRef.current?.pause();
    }, [isCatalogVideoActive]);

    return {
        videoRef,
        containerRef,
        progress,
        actuallyLoadVideo,
        showVideo: Boolean(videoSrc && hasPresentedFrame && isCatalogVideoActive),
        handleCanPlayThrough: markVideoReady,
        handleProgress,
        handlePlaying: () => {
            markVideoReady();
            revealVideoAfterFirstFrame();
        },
        handlePlaybackInterruption: hideVideoUntilFirstFrame,
        handleError: () => {
            setVideoReady(false);
            hideVideoUntilFirstFrame();
            if (videoSrc) setVideoStatus(queueId, 'error');
        },
    };
};
