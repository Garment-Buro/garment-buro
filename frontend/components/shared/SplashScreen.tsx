"use client";

import type { SplashController } from '@/hooks/browser/useSplashController';

export const SplashScreen = ({ controller }: { controller: SplashController }) => {
    const {
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
    } = controller;

    if (isHiddenRoute || !show) return null;

    return (
        <>
            {/* Preload the background image to avoid gray flash */}
            <link rel="preload" href="/landing-bg.webp" as="image" type="image/webp" />
            <link rel="preload" href="/logo_anim.mp4" as="video" type="video/mp4" />
            <div
                className="appSplashScreen"
                onClick={dismiss}
                style={{
                    position: 'fixed',
                    inset: 0,
                    zIndex: 9999,
                    backgroundImage: 'url("/landing-bg.webp")',
                    backgroundSize: 'cover',
                    backgroundPosition: 'center',
                    backgroundRepeat: 'no-repeat',
                    backgroundColor: '#F2F2F2', // fallback same as body
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    transition: 'opacity 0.65s ease',
                    opacity: exiting ? 0 : 1,
                    pointerEvents: exiting ? 'none' : 'auto',
                }}
            >
                {/* Logo + Text row — centered as one unit */}
                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        userSelect: 'none',
                    }}
                >
                    {/* Text — slides in from left as logo shifts right */}
                    <div
                        style={{
                            overflow: 'hidden',
                            maxWidth: revealed ? '700px' : '0px',
                            opacity: revealed ? 1 : 0,
                            transition: [
                                'max-width 1.3s cubic-bezier(0.25, 0.46, 0.45, 0.94)',
                                'opacity 0.6s ease-out 0.1s',
                            ].join(', '),
                        }}
                    >
                        <span
                            style={{
                                display: 'block',
                                fontFamily: 'var(--font-michroma), Michroma, sans-serif',
                                color: '#1a1a1a',
                                whiteSpace: 'nowrap',
                                lineHeight: 2,
                                paddingRight: 'clamp(14px, 2.5vw, 32px)',
                                fontSize: 'clamp(16px, 3.2vw, 42px)',
                                letterSpacing: '0.04em',
                            }}
                        >
                            Garment Buro
                        </span>
                    </div>

                    {/* Logo ball */}
                    <div
                        style={{
                            position: 'relative',
                            width: 'clamp(120px, 18vw, 200px)',
                            height: 'clamp(120px, 18vw, 200px)',
                            flexShrink: 0,
                            borderRadius: '50%',
                            overflow: 'hidden',
                            opacity: logoReady ? 1 : 0,
                            transition: 'opacity 120ms ease-out',
                        }}
                        >
                        <video
                            ref={videoRef}
                            src="/logo_anim.mp4"
                            autoPlay
                            loop
                            muted
                            playsInline
                            controls={false}
                            disablePictureInPicture
                            controlsList="nodownload nofullscreen noremoteplayback"
                            preload="auto"
                            onLoadedMetadata={tryPlayLogo}
                            onCanPlayThrough={tryPlayLogo}
                            onCanPlay={tryPlayLogo}
                            onLoadedData={tryPlayLogo}
                            onPlaying={handleLogoPlaying}
                            onError={handleLogoError}
                            onStalled={tryPlayLogo}
                            onWaiting={tryPlayLogo}
                            style={{
                                position: 'absolute',
                                inset: 0,
                                width: '100%',
                                height: '100%',
                                objectFit: 'cover',
                                display: 'block',
                                pointerEvents: 'none',
                            }}
                        />
                    </div>
                </div>

                {/* Hint at the bottom */}
                <div
                    style={{
                        position: 'absolute',
                        bottom: '32px',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        transition: 'opacity 0.7s ease 1.5s',
                        opacity: revealed ? 1 : 0,
                        pointerEvents: 'none',
                    }}
                >
                    <span
                        className="splash-hint-pulse"
                        style={{
                            fontFamily: 'var(--font-michroma), Michroma, sans-serif',
                            color: 'rgba(0,0,0,0.35)',
                            fontSize: '10px',
                            letterSpacing: '0.22em',
                            textTransform: 'uppercase',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        нажмите, чтобы войти
                    </span>
                </div>
            </div>
        </>
    );
};
