"use client";

import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

export function useVideoFrameReveal(videoRef: RefObject<HTMLVideoElement | null>) {
    const [hasPresentedFrame, setHasPresentedFrame] = useState(false);
    const callbackVideoRef = useRef<HTMLVideoElement | null>(null);
    const videoFrameCallbackIdRef = useRef<number | null>(null);
    const fallbackTimerRef = useRef<number | null>(null);

    const cancelPendingReveal = useCallback(() => {
        if (callbackVideoRef.current && videoFrameCallbackIdRef.current !== null) {
            callbackVideoRef.current.cancelVideoFrameCallback(videoFrameCallbackIdRef.current);
        }

        if (fallbackTimerRef.current !== null) {
            window.clearTimeout(fallbackTimerRef.current);
        }

        callbackVideoRef.current = null;
        videoFrameCallbackIdRef.current = null;
        fallbackTimerRef.current = null;
    }, []);

    const hideVideoUntilFirstFrame = useCallback(() => {
        cancelPendingReveal();
        setHasPresentedFrame(false);
    }, [cancelPendingReveal]);

    const revealVideoAfterFirstFrame = useCallback(() => {
        cancelPendingReveal();

        const video = videoRef.current;
        if (!video) return;

        if (typeof video.requestVideoFrameCallback === "function") {
            callbackVideoRef.current = video;
            videoFrameCallbackIdRef.current = video.requestVideoFrameCallback(() => {
                callbackVideoRef.current = null;
                videoFrameCallbackIdRef.current = null;

                if (!video.paused && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
                    setHasPresentedFrame(true);
                }
            });
            return;
        }

        fallbackTimerRef.current = window.setTimeout(() => {
            fallbackTimerRef.current = null;
            if (!video.paused && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
                setHasPresentedFrame(true);
            }
        }, 50);
    }, [cancelPendingReveal, videoRef]);

    useEffect(() => cancelPendingReveal, [cancelPendingReveal]);

    return {
        hasPresentedFrame,
        hideVideoUntilFirstFrame,
        revealVideoAfterFirstFrame,
    };
}
