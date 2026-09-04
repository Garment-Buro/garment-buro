'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';

import styles from './CollectionLanding.module.css';

export const LandingReveal = ({ children, className = '' }: { children: ReactNode; className?: string }) => {
    const ref = useRef<HTMLDivElement>(null);
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        const element = ref.current;
        if (!element) return;
        const observer = new IntersectionObserver(([entry]) => {
            if (!entry.isIntersecting) return;
            setVisible(true);
            observer.disconnect();
        }, { rootMargin: '0px 0px -12% 0px' });
        observer.observe(element);
        return () => observer.disconnect();
    }, []);

    return (
        <div ref={ref} className={`${styles.reveal} ${visible ? styles.revealVisible : ''} ${className}`}>
            {children}
        </div>
    );
};

export const LandingWordReveal = ({ text }: { text: string }) => {
    const ref = useRef<HTMLHeadingElement>(null);
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        const element = ref.current;
        if (!element) return;
        const observer = new IntersectionObserver(([entry]) => {
            if (!entry.isIntersecting) return;
            setVisible(true);
            observer.disconnect();
        }, { threshold: 0.45 });
        observer.observe(element);
        return () => observer.disconnect();
    }, []);

    return (
        <h2 ref={ref} className={styles.tagline} aria-label={text}>
            {text.split(/\s+/).map((word, index) => (
                <span
                    key={`${word}-${index}`}
                    aria-hidden="true"
                    className={visible ? styles.taglineWordVisible : styles.taglineWord}
                    style={{ transitionDelay: `${index * 55}ms` }}
                >
                    {word}{' '}
                </span>
            ))}
        </h2>
    );
};
