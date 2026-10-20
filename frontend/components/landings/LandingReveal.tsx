'use client';

import { useEffect, useRef, type ReactNode } from 'react';

import styles from './CollectionLanding.module.css';

function useLandingReveal<Element extends HTMLElement>(rootMargin = '0px', threshold = 0) {
    const ref = useRef<Element>(null);
    useEffect(() => {
        const element = ref.current;
        if (!element || typeof IntersectionObserver === 'undefined'
            || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        // Server HTML and already visible content stay readable. Only arm
        // offscreen reveals after the browser has initialized this effect.
        if (element.getBoundingClientRect().top < window.innerHeight) return;
        element.dataset.landingRevealPending = 'true';
        const observer = new IntersectionObserver(([entry]) => {
            if (!entry.isIntersecting) return;
            delete element.dataset.landingRevealPending;
            observer.disconnect();
        }, { rootMargin, threshold });
        observer.observe(element);
        return () => {observer.disconnect(); delete element.dataset.landingRevealPending};
    }, [rootMargin, threshold]);
    return ref;
}

export const LandingReveal = ({ children, className = '' }: { children: ReactNode; className?: string }) => {
    const ref = useLandingReveal<HTMLDivElement>('0px 0px -12% 0px');

    return (
        <div ref={ref} className={`${styles.reveal} ${className}`}>
            {children}
        </div>
    );
};

export const LandingWordReveal = ({ text }: { text: string }) => {
    const ref = useLandingReveal<HTMLHeadingElement>('0px', 0.45);

    return (
        <h2 ref={ref} className={styles.tagline} aria-label={text}>
            {text.split(/\s+/).map((word, index) => (
                <span
                    key={`${word}-${index}`}
                    aria-hidden="true"
                    className={styles.taglineWord}
                    style={{ transitionDelay: `${index * 55}ms` }}
                >
                    {word}{' '}
                </span>
            ))}
        </h2>
    );
};
