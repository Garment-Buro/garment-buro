"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import { uploadMediaFile } from '@/lib/api/uploads';
import { useSettingsStore } from '@/store/settingsStore';
import { runCatalogWrite } from '@/store/catalogWrite';
import { useVideoQueue } from '@/store/videoQueueStore';

export const useAnimatedLogo = () => {
    const pathname = usePathname();
    const settings = useSettingsStore((state) => state.settings);
    const fetchSettings = useSettingsStore((state) => state.fetchSettings);
    const updateSettings = useSettingsStore((state) => state.updateSettings);
    const registerVideo = useVideoQueue((state) => state.registerVideo);
    const unregisterVideo = useVideoQueue((state) => state.unregisterVideo);
    const setVideoStatus = useVideoQueue((state) => state.setVideoStatus);
    const [isHovered, setIsHovered] = useState(false);
    const [isScrolled, setIsScrolled] = useState(false);
    const [logoReady, setLogoReady] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const videoRef = useRef<HTMLVideoElement>(null);

    useEffect(() => {
        if (pathname !== '/') return;

        const onScroll = () => setIsScrolled(window.scrollY > 80);
        window.addEventListener('scroll', onScroll, { passive: true });
        return () => window.removeEventListener('scroll', onScroll);
    }, [pathname]);

    useEffect(() => {
        registerVideo('logo', 0);
        return () => unregisterVideo('logo');
    }, [registerVideo, unregisterVideo]);

    useEffect(() => {
        if (!settings) void fetchSettings();
    }, [settings, fetchSettings]);

    const videoUrl = settings?.logo_video_url || '/logo_anim.mp4';

    const tryPlayLogo = useCallback(() => {
        const maybePromise = videoRef.current?.play();
        if (maybePromise && typeof maybePromise.catch === 'function') {
            maybePromise.catch(() => undefined);
        }
    }, []);

    const handleLogoReady = useCallback(() => {
        if (!logoReady) {
            setLogoReady(true);
            window.setTimeout(() => setVideoStatus('logo', 'loaded'), 1000);
        }
        tryPlayLogo();
    }, [logoReady, setVideoStatus, tryPlayLogo]);

    useEffect(() => {
        tryPlayLogo();

        const handleVisibilityChange = () => {
            if (!document.hidden) tryPlayLogo();
        };

        document.addEventListener('visibilitychange', handleVisibilityChange);
        return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
    }, [tryPlayLogo, videoUrl]);

    const handleFileChange = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        try {
            const url = await runCatalogWrite(token => uploadMediaFile(file, token));
            await updateSettings({ logo_video_url: url });
        } catch (error) {
            console.error('Upload failed', error);
        }
    }, [updateSettings]);

    return {
        pathname,
        isEditing: pathname === '/admin/editor',
        isHovered,
        isScrolled,
        videoUrl,
        fileInputRef,
        videoRef,
        handleFileChange,
        handleLogoReady,
        openFilePicker: () => fileInputRef.current?.click(),
        setIsHovered,
    };
};
