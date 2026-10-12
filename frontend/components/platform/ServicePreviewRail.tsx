'use client';

import { useEffect, useRef, type ReactNode } from 'react';

import styles from './ServiceHome.module.css';

/** A slow, reversible preview pan; touch, keyboard and reduced motion take priority. */
export function ServicePreviewRail({ children, className, label }: {
    children: ReactNode;
    className: string;
    label: string;
}) {
    const railRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const rail = railRef.current;
        if (!rail) return;
        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
        let frame = 0;
        let lastTime = 0;
        let resumeAt = performance.now() + 2000;
        let direction = 1;
        let position = rail.scrollLeft;
        let limit = 0;
        let hovering = false;
        let touching = false;
        const measure = () => { limit = Math.max(0, rail.scrollWidth - rail.clientWidth); };
        measure();

        const tick = (time: number) => {
            const elapsed = lastTime ? Math.min(time - lastTime, 40) : 0;
            lastTime = time;
            if (limit > 1 && time >= resumeAt && !hovering && !touching && !rail.matches(':focus-within')) {
                const next = position + direction * elapsed * .012;
                position = Math.max(0, Math.min(limit, next));
                rail.scrollLeft = position;
                if (next >= limit || next <= 0) {
                    direction *= -1;
                    resumeAt = time + 1500;
                }
            } else position = rail.scrollLeft;
            frame = requestAnimationFrame(tick);
        };
        const syncPlayback = () => {
            cancelAnimationFrame(frame);
            lastTime = 0;
            if (limit > 1 && !reducedMotion.matches && !document.hidden) frame = requestAnimationFrame(tick);
        };
        const observer = new ResizeObserver(() => { measure(); syncPlayback(); });
        observer.observe(rail);
        Array.from(rail.children).forEach(child => observer.observe(child));
        const pause = () => { resumeAt = performance.now() + 6000; };
        const enter = () => { hovering = true; };
        const leave = () => { hovering = false; pause(); };
        const touchStart = () => { touching = true; pause(); };
        const touchEnd = () => { if (touching) { touching = false; pause(); } };

        rail.addEventListener('mouseenter', enter);
        rail.addEventListener('mouseleave', leave);
        rail.addEventListener('pointerdown', touchStart);
        window.addEventListener('pointerup', touchEnd);
        window.addEventListener('pointercancel', touchEnd);
        rail.addEventListener('wheel', pause, { passive: true });
        rail.addEventListener('focusout', pause);
        document.addEventListener('visibilitychange', syncPlayback);
        reducedMotion.addEventListener('change', syncPlayback);
        syncPlayback();

        return () => {
            cancelAnimationFrame(frame);
            observer.disconnect();
            rail.removeEventListener('mouseenter', enter);
            rail.removeEventListener('mouseleave', leave);
            rail.removeEventListener('pointerdown', touchStart);
            window.removeEventListener('pointerup', touchEnd);
            window.removeEventListener('pointercancel', touchEnd);
            rail.removeEventListener('wheel', pause);
            rail.removeEventListener('focusout', pause);
            document.removeEventListener('visibilitychange', syncPlayback);
            reducedMotion.removeEventListener('change', syncPlayback);
        };
    }, [children]);

    return <div ref={railRef} className={`${styles.rail} ${className}`} tabIndex={0} role="group" aria-label={label}>
        {children}
    </div>;
}
