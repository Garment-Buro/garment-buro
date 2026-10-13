'use client';

import { useEffect, useRef, type ReactNode } from 'react';

import { getPreviewPan } from './servicePreviewMotion';

import styles from './ServiceHome.module.css';

type PreviewRailProps = {
    children: ReactNode;
    className: string;
    label: string;
    resetKey?: string;
    autoPlay?: boolean;
};

/** Remounting on search resets both the native scroll and the motion lifecycle. */
export function ServicePreviewRail({ resetKey, ...props }: PreviewRailProps) {
    return <PreviewRail key={resetKey} {...props} />;
}

function PreviewRail({ children, className, label, autoPlay = true }: PreviewRailProps) {
    const railRef = useRef<HTMLDivElement>(null);
    const trackRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const rail = railRef.current;
        const track = trackRef.current;
        if (!autoPlay || !rail || !track || typeof track.animate !== 'function') return;

        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
        let animation: Animation | null = null;
        let interacted = false;
        let hovered = false;
        let inView = true;

        const stop = (preservePosition: boolean) => {
            if (!animation) return;
            // Transfer the visual offset once, so native scrolling starts without a jump.
            const offset = preservePosition ? -new DOMMatrixReadOnly(getComputedStyle(track).transform).m41 : 0;
            animation.cancel();
            animation = null;
            track.style.willChange = '';
            if (preservePosition) rail.scrollLeft += offset;
        };
        const syncPlayback = () => {
            if (!animation) return;
            if (document.hidden || !inView || hovered || reducedMotion.matches) animation.pause();
            else animation.play();
        };
        const measure = () => {
            stop(false);
            if (interacted || reducedMotion.matches) return;
            const railStyle = getComputedStyle(rail);
            const width = rail.clientWidth - parseFloat(railStyle.paddingLeft) - parseFloat(railStyle.paddingRight);
            const pan = getPreviewPan(width, track.offsetWidth);
            if (!pan) return;
            track.style.willChange = 'transform';
            animation = track.animate([
                { transform: 'translateX(0)' },
                { transform: `translateX(-${pan.distance}px)` },
            ], { duration: pan.duration, delay: 1500, iterations: Infinity, direction: 'alternate', easing: 'linear', fill: 'both' });
            syncPlayback();
        };
        const takeOver = () => { interacted = true; stop(true); };
        const enter = () => { hovered = true; syncPlayback(); };
        const leave = () => { hovered = false; syncPlayback(); };
        const preferenceChanged = () => { if (reducedMotion.matches) stop(true); else measure(); };
        const resizeObserver = new ResizeObserver(measure);
        resizeObserver.observe(rail);
        resizeObserver.observe(track);
        const intersectionObserver = new IntersectionObserver(entries => {
            inView = entries[0].isIntersecting;
            syncPlayback();
        });
        intersectionObserver.observe(rail);
        rail.addEventListener('pointerdown', takeOver, { passive: true });
        rail.addEventListener('wheel', takeOver, { passive: true });
        rail.addEventListener('scroll', takeOver, { passive: true });
        rail.addEventListener('focusin', takeOver);
        rail.addEventListener('mouseenter', enter);
        rail.addEventListener('mouseleave', leave);
        document.addEventListener('visibilitychange', syncPlayback);
        reducedMotion.addEventListener('change', preferenceChanged);
        measure();

        return () => {
            stop(false);
            resizeObserver.disconnect();
            intersectionObserver.disconnect();
            rail.removeEventListener('pointerdown', takeOver);
            rail.removeEventListener('wheel', takeOver);
            rail.removeEventListener('scroll', takeOver);
            rail.removeEventListener('focusin', takeOver);
            rail.removeEventListener('mouseenter', enter);
            rail.removeEventListener('mouseleave', leave);
            document.removeEventListener('visibilitychange', syncPlayback);
            reducedMotion.removeEventListener('change', preferenceChanged);
        };
    }, [autoPlay]);

    return <div ref={railRef} className={`${styles.rail} ${className}`} tabIndex={0} role="group" aria-label={label}>
        <div ref={trackRef} className={styles.railTrack}>{children}</div>
    </div>;
}
