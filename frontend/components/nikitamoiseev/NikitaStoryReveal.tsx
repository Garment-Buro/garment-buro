'use client';

import { useEffect, useRef } from 'react';

import styles from './NikitaMoiseevLanding.module.css';

const lines = ['NIKITA', 'MOISEEV', 'GARMENT', 'BURO'];

export const NikitaStoryReveal = () => {
    const rootRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const root = rootRef.current;
        if (!root) return;

        let frame = 0;
        const update = () => {
            frame = 0;
            const section = root.closest('section');
            if (!section) return;
            const rect = section.getBoundingClientRect();
            const travel = Math.max(1, window.innerHeight * 0.78);
            const progress = Math.min(1, Math.max(0, (window.innerHeight * 0.8 - rect.top) / travel));
            root.querySelectorAll<HTMLElement>('[data-story-line]').forEach((line, index) => {
                const lineProgress = Math.min(1, Math.max(0, progress * lines.length - index));
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
            {lines.map((line) => (
                <span key={line} data-story-line>{line}</span>
            ))}
        </div>
    );
};
