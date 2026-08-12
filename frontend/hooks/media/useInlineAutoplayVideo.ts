"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export const useInlineAutoplayVideo = () => {
    const videoRef = useRef<HTMLVideoElement | null>(null);
    const [hasPlayingFrame, setHasPlayingFrame] = useState(false);

    const tryPlay = useCallback(() => {
        const video = videoRef.current;
        if (!video) return;

        video.muted = true;
        video.defaultMuted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute("muted", "");
        video.setAttribute("autoplay", "");
        video.setAttribute("playsinline", "");
        video.setAttribute("webkit-playsinline", "");
        video.removeAttribute("controls");

        const maybePromise = video.play();
        if (maybePromise && typeof maybePromise.catch === "function") {
            maybePromise.catch(() => undefined);
        }
    }, []);

    useEffect(() => {
        const retryTimers = [0, 180, 600].map((delay) => window.setTimeout(tryPlay, delay));
        const resumePlayback = () => tryPlay();
        const handleVisibilityChange = () => {
            if (!document.hidden) resumePlayback();
        };

        window.addEventListener("pageshow", resumePlayback);
        document.addEventListener("visibilitychange", handleVisibilityChange);

        return () => {
            retryTimers.forEach((timer) => window.clearTimeout(timer));
            window.removeEventListener("pageshow", resumePlayback);
            document.removeEventListener("visibilitychange", handleVisibilityChange);
        };
    }, [tryPlay]);

    return {
        videoRef,
        hasPlayingFrame,
        tryPlay,
        handlePlaying: () => setHasPlayingFrame(true),
        handleError: () => setHasPlayingFrame(false),
    };
};
