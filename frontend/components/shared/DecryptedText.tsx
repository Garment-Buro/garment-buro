"use client";

import { motion } from "framer-motion";

import { useDecryptedText } from "@/hooks/ui/useDecryptedText";
import type { TextRevealDirection } from "@/lib/text/utils/decryptedText";

interface DecryptedTextProps {
    text: string;
    speed?: number;
    maxIterations?: number;
    characters?: string;
    className?: string;
    parentClassName?: string;
    encryptedClassName?: string;
    animateOn?: "hover" | "view" | "click" | "none";
    clickMode?: "once" | "toggle";
    revealDirection?: TextRevealDirection;
    sequential?: boolean;
    useOriginalCharsOnly?: boolean;
}

const DEFAULT_CHARS = "ABCDEFGHJKLMNOPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz1234567890!@#$%^&*()_+-=[]{}|;':\",./<>?";

export function DecryptedText({
    text,
    speed = 50,
    maxIterations = 10,
    characters = DEFAULT_CHARS,
    className = "",
    parentClassName = "",
    encryptedClassName = "",
    animateOn = "hover",
    clickMode = "once",
    revealDirection = "start",
    sequential = false,
    useOriginalCharsOnly = false,
}: DecryptedTextProps) {
    const {
        containerRef,
        measureRef,
        displayText,
        isAnimating,
        stableWidth,
        handleInteraction,
        handleMouseEnter,
    } = useDecryptedText({
        text,
        speed,
        maxIterations,
        characters,
        animateOn,
        clickMode,
        revealDirection,
        sequential,
        useOriginalCharsOnly,
        measureDependency: className,
    });

    return (
        <motion.span
            ref={containerRef}
            className={`relative inline-block align-baseline ${parentClassName}`}
            style={stableWidth ? { width: stableWidth } : undefined}
            onMouseEnter={handleMouseEnter}
            onClick={handleInteraction}
        >
            <span
                ref={measureRef}
                className={`${className} invisible pointer-events-none absolute left-0 top-0 whitespace-nowrap`}
                aria-hidden="true"
            >
                {text}
            </span>
            <span className={`${className} ${isAnimating ? encryptedClassName : ""} block overflow-hidden whitespace-nowrap`}>
                {displayText}
            </span>
        </motion.span>
    );
}
