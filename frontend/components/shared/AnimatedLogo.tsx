"use client";

import React, { CSSProperties } from 'react';
import NextLink from 'next/link';
import { useAnimatedLogo } from '@/hooks/layout/useAnimatedLogo';
import { MEDIA_FILE_ACCEPT } from '@/lib/media/utils/upload';

export const AnimatedLogo = () => {
    const {
        pathname,
        isEditing,
        isHovered,
        isScrolled,
        videoUrl,
        fileInputRef,
        videoRef,
        handleFileChange,
        handleLogoReady,
        openFilePicker,
        setIsHovered,
    } = useAnimatedLogo();

    if (pathname === '/checkout' || pathname === '/constructor' || pathname === '/unfinished' || pathname === '/lk') return null;

    const isProductPage = pathname.startsWith('/product');
    const isProductEditor = isEditing && false; // Future-proofing if editor handles product viewing
    const useSmallLogo = isProductPage || isProductEditor;

    const baseClasses = "fixed z-[110] md:z-[100] rounded-full mix-blend-multiply opacity-80 [backface-visibility:hidden] [contain:layout_paint_style]";
    const editClasses = isEditing ? 'pointer-events-auto cursor-pointer border border-dashed border-transparent hover:border-black' : 'cursor-pointer overflow-hidden';

    const mobileSizeClasses = useSmallLogo
        ? "top-[30px] left-1/2 -translate-x-1/2 -translate-y-1/2 w-[28px] h-[28px] block"
        : isScrolled
            ? "top-[30px] left-1/2 -translate-x-1/2 w-[31px] h-[31px] block"
            : "top-[50px] left-1/2 -translate-x-1/2 w-[31px] h-[31px] block";

    const desktopMotionClasses = "md:top-0 md:left-0 md:w-[75px] md:h-[75px] md:translate-x-0 md:translate-y-0 md:[transform:translate3d(var(--logo-x),var(--logo-y),0)_scale(var(--logo-scale))] md:[transform-origin:top_left] md:transition-transform md:duration-300 md:ease-out md:[will-change:transform]";

    const desktopLogoStyle = {
        '--logo-x': useSmallLogo ? '70px' : 'calc(50vw - 37.5px)',
        '--logo-y': useSmallLogo ? '45px' : (isScrolled ? '10px' : '30px'),
        '--logo-scale': useSmallLogo ? String(38 / 75) : '1',
    } as CSSProperties;

    const logoClasses = `${baseClasses} ${mobileSizeClasses} ${desktopMotionClasses} ${editClasses}`;

    const content = (
        <>
            <video
                ref={videoRef}
                key={videoUrl} // Force remount if url changes
                src={videoUrl}
                autoPlay
                loop
                muted
                playsInline
                preload="auto"
                onCanPlayThrough={handleLogoReady}
                onCanPlay={handleLogoReady}
                onLoadedData={handleLogoReady}
                onPlaying={handleLogoReady}
                className={`w-full h-full object-cover ${!isEditing ? '' : 'rounded-full'}`}
            />

            {isEditing && isHovered && (
                <div className="absolute inset-0 bg-black/50 rounded-full flex items-center justify-center">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                </div>
            )}

            <input
                type="file"
                accept={MEDIA_FILE_ACCEPT}
                ref={fileInputRef}
                className="hidden"
                onChange={handleFileChange}
            />
        </>
    );

    if (!isEditing) {
        return (
            <NextLink
                href="/"
                className={logoClasses}
                style={desktopLogoStyle}
            >
                {content}
            </NextLink>
        );
    }

    return (
        <div
            className={logoClasses}
            style={desktopLogoStyle}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            onClick={openFilePicker}
        >
            {content}
        </div>
    );
};
