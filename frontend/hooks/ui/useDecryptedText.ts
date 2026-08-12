"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { useInView } from 'framer-motion';

import {
    createDecryptedTextFrame,
    getRandomTextCharacter,
    randomizeText,
    type TextRevealDirection,
} from '@/lib/text/utils/decryptedText';

type UseDecryptedTextOptions = {
    text: string;
    speed: number;
    maxIterations: number;
    characters: string;
    animateOn: 'hover' | 'view' | 'click' | 'none';
    clickMode: 'once' | 'toggle';
    revealDirection: TextRevealDirection;
    sequential: boolean;
    useOriginalCharsOnly: boolean;
    measureDependency: string;
};

export const useDecryptedText = ({
    text,
    speed,
    maxIterations,
    characters,
    animateOn,
    clickMode,
    revealDirection,
    sequential,
    useOriginalCharsOnly,
    measureDependency,
}: UseDecryptedTextOptions) => {
    const [displayText, setDisplayText] = useState(text);
    const [isAnimating, setIsAnimating] = useState(false);
    const [isDecrypted, setIsDecrypted] = useState(false);
    const [stableWidth, setStableWidth] = useState<number | null>(null);
    const animationRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const containerRef = useRef<HTMLSpanElement>(null);
    const measureRef = useRef<HTMLSpanElement>(null);
    const isInView = useInView(containerRef, { once: true });
    const isFirstTextChangeRef = useRef(true);

    const getRandomCharacter = useCallback((originalChar: string) => getRandomTextCharacter({
        originalChar,
        sourceText: text,
        characters,
        useOriginalCharsOnly,
    }), [characters, text, useOriginalCharsOnly]);

    const startAnimation = useCallback(() => {
        if (isAnimating) return;
        setIsAnimating(true);
        let iteration = 0;

        if (animationRef.current) clearInterval(animationRef.current);
        animationRef.current = setInterval(() => {
            setDisplayText(createDecryptedTextFrame({
                text,
                iteration,
                totalIterations: maxIterations,
                revealDirection,
                sequential,
                getRandomCharacter,
            }));
            iteration += 1;

            if (iteration > maxIterations) {
                if (animationRef.current) clearInterval(animationRef.current);
                setDisplayText(text);
                setIsAnimating(false);
                setIsDecrypted(true);
            }
        }, speed);
    }, [getRandomCharacter, isAnimating, maxIterations, revealDirection, sequential, speed, text]);

    useEffect(() => {
        if (isFirstTextChangeRef.current) {
            isFirstTextChangeRef.current = false;
            return;
        }
        if (text === displayText || isAnimating) return;
        const animationFrameId = window.requestAnimationFrame(startAnimation);
        return () => window.cancelAnimationFrame(animationFrameId);
    }, [displayText, isAnimating, startAnimation, text]);

    useEffect(() => {
        if (animateOn !== 'view' || !isInView || isDecrypted) return;
        const animationFrameId = window.requestAnimationFrame(startAnimation);
        return () => window.cancelAnimationFrame(animationFrameId);
    }, [animateOn, isDecrypted, isInView, startAnimation]);

    useEffect(() => () => {
        if (animationRef.current) clearInterval(animationRef.current);
    }, []);

    useEffect(() => {
        const measureElement = measureRef.current;
        if (!measureElement) return;
        const updateWidth = () => {
            const width = measureElement.getBoundingClientRect().width;
            setStableWidth(width > 0 ? Math.ceil(width) : null);
        };

        updateWidth();
        if (typeof ResizeObserver === 'undefined') {
            window.addEventListener('resize', updateWidth);
            return () => window.removeEventListener('resize', updateWidth);
        }

        const observer = new ResizeObserver(updateWidth);
        observer.observe(measureElement);
        return () => observer.disconnect();
    }, [measureDependency, text]);

    const handleInteraction = () => {
        if (animateOn !== 'click') return;
        if (clickMode === 'once' && isDecrypted) return;
        if (clickMode === 'toggle' && isDecrypted) {
            setDisplayText(randomizeText(text, getRandomCharacter));
            setIsDecrypted(false);
            return;
        }
        startAnimation();
    };

    const handleMouseEnter = () => {
        if (animateOn === 'hover') startAnimation();
    };

    return {
        containerRef,
        measureRef,
        displayText,
        isAnimating,
        stableWidth,
        handleInteraction,
        handleMouseEnter,
    };
};
