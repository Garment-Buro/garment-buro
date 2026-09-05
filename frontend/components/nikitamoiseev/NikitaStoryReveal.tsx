'use client';

import { useEffect, useRef } from 'react';

import styles from './NikitaMoiseevLanding.module.css';
import { STORY_OUTLINES } from './storyOutlines';

export const NikitaStoryReveal = () => {
    const rootRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const root = rootRef.current;
        if (!root) return;

        let frame = 0;
        const update = () => {
            frame = 0;
            const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            root.querySelectorAll<HTMLElement>('[data-story-line]').forEach((line) => {
                // Start only when this actual line reaches the lower-middle of
                // the screen, rather than when the distant section enters it.
                const rect = line.getBoundingClientRect();
                const travel = Math.max(rect.height * 1.5, window.innerHeight * 0.22);
                const lineProgress = reducedMotion ? 1 : Math.min(1, Math.max(0, (window.innerHeight * 0.65 - rect.top) / travel));
                line.style.setProperty('--story-line-hidden', `${(1 - lineProgress) * 100}%`);
            });
        };
        const schedule = () => {
            if (frame) return;
            frame = window.requestAnimationFrame(update);
        };

        update();
        window.addEventListener('scroll', schedule, { passive: true });
        window.addEventListener('resize', schedule);
        return () => {
            window.removeEventListener('scroll', schedule);
            window.removeEventListener('resize', schedule);
            window.cancelAnimationFrame(frame);
        };
    }, []);

    return (
        <div ref={rootRef} className={styles.collectionNames} aria-hidden="true">
            {STORY_OUTLINES.map((line) => (
                <span key={line.label} data-story-line>
                    <svg viewBox={`0 0 ${line.width} 1000`} style={{ width: `${line.width / 1000}em` }} aria-hidden="true">
                        <path d={line.path} fill="none" stroke="currentColor" strokeWidth="1.3" vectorEffect="non-scaling-stroke" />
                    </svg>
                </span>
            ))}
        </div>
    );
};
