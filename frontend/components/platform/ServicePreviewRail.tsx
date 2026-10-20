'use client';

import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';

import { getPreviewPan, type PreviewDirection } from './servicePreviewMotion';

import styles from './ServiceHome.module.css';

type PreviewRailProps = {
    children: ReactNode;
    className: string;
    label: string;
    resetKey?: string;
    autoPlay?: boolean;
    direction?: PreviewDirection;
};

/** Remounting on search resets both the native scroll and the motion lifecycle. */
export function ServicePreviewRail({ resetKey, ...props }: PreviewRailProps) {
    return <PreviewRail key={resetKey} {...props} />;
}

function PreviewRail({ children, className, label, autoPlay = true, direction = 'left' }: PreviewRailProps) {
    const railRef = useRef<HTMLDivElement>(null);
    const trackRef = useRef<HTMLDivElement>(null);
    const firstSetRef = useRef<HTMLDivElement>(null);
    const nextSetRef = useRef<HTMLDivElement>(null);
    const interacted = useRef(false);
    const [copies, setCopies] = useState(autoPlay ? 2 : 1);

    useLayoutEffect(() => {
        const rail = railRef.current;
        const track = trackRef.current;
        if (!autoPlay || !rail || !track || typeof track.animate !== 'function') return;

        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
        let animation: Animation | null = null;
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
            if (reducedMotion.matches) { setCopies(1); return; }
            if (interacted.current) return;
            const first = firstSetRef.current?.firstElementChild;
            const next = nextSetRef.current?.firstElementChild;
            if (!first) return;
            if (!next) { setCopies(2); return; }
            const railStyle = getComputedStyle(rail);
            const width = rail.clientWidth - parseFloat(railStyle.paddingLeft) - parseFloat(railStyle.paddingRight);
            // Measure matching cards so the period includes the exact gap/overlap in WebKit too.
            const cycle = next.getBoundingClientRect().left - first.getBoundingClientRect().left;
            const pan = getPreviewPan(width, cycle, direction);
            if (!pan) return;
            if (copies !== pan.copies) { setCopies(pan.copies); return; }
            rail.scrollLeft = 0;
            track.style.willChange = 'transform';
            animation = track.animate([
                { transform: `translateX(${pan.from}px)` },
                { transform: `translateX(${pan.to}px)` },
            ], { duration: pan.duration, iterations: Infinity, easing: 'linear', fill: 'both' });
            syncPlayback();
        };
        const takeOver = () => { interacted.current = true; stop(true); };
        const scroll = () => { if (animation && rail.scrollLeft > 0) takeOver(); };
        const enter = () => { hovered = true; syncPlayback(); };
        const leave = () => { hovered = false; syncPlayback(); };
        const preferenceChanged = () => { stop(true); measure(); };
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
        rail.addEventListener('scroll', scroll, { passive: true });
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
            rail.removeEventListener('scroll', scroll);
            rail.removeEventListener('focusin', takeOver);
            rail.removeEventListener('mouseenter', enter);
            rail.removeEventListener('mouseleave', leave);
            document.removeEventListener('visibilitychange', syncPlayback);
            reducedMotion.removeEventListener('change', preferenceChanged);
        };
    }, [autoPlay, copies, direction]);

    return <div ref={railRef} className={`${styles.rail} ${className}`} tabIndex={0} role="group" aria-label={label}>
        <div ref={trackRef} className={styles.railTrack}>
            {Array.from({ length: autoPlay ? copies : 1 }, (_, copy) => <div
                key={copy}
                className={styles.railSet}
                aria-hidden={copy > 0 || undefined}
                ref={node => {
                    if (copy === 0) firstSetRef.current = node;
                    if (copy === 1) nextSetRef.current = node;
                    // Visual copies keep their click handlers but add no duplicate keyboard stops.
                    if (copy > 0) node?.querySelectorAll<HTMLElement>('button, a, input, select, textarea, [tabindex]').forEach(element => { element.tabIndex = -1; });
                }}
            >{children}</div>)}
        </div>
    </div>;
}
