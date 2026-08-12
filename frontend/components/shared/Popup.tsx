"use client";

import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useRouter } from 'next/navigation';

interface PopupProps {
    children: React.ReactNode;
    /** Called when the popup is closed. Defaults to router.back() */
    onClose?: () => void;
    /** Max width of the popup panel. Defaults to 600px */
    maxWidth?: number;
    /** Show the X close button. Defaults to true */
    showClose?: boolean;
    /** Optional panel class override, such as a custom background */
    panelClassName?: string;
    /** Optional viewport insets for fixed overlays */
    viewportStyle?: React.CSSProperties;
    /** Optional backdrop classes. Defaults to the shared frosted overlay. */
    backdropClassName?: string;
}

export const Popup: React.FC<PopupProps> = ({
    children,
    onClose,
    maxWidth = 600,
    showClose = true,
    panelClassName,
    viewportStyle,
    backdropClassName = "bg-black/40 backdrop-blur-[3px]",
}) => {
    const router = useRouter();
    const panelRef = useRef<HTMLDivElement>(null);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    const handleClose = () => {
        if (onClose) {
            onClose();
        } else {
            router.back();
        }
    };

    // Close on Escape key
    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') handleClose();
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Lock the page in place while the fixed overlay is open, including iOS/PWA.
    useEffect(() => {
        const scrollY = window.scrollY;
        const lockedPathname = window.location.pathname;
        const html = document.documentElement;
        const body = document.body;
        const previousHtmlOverflow = html.style.overflow;
        const previousBodyOverflow = body.style.overflow;
        const previousBodyPosition = body.style.position;
        const previousBodyTop = body.style.top;
        const previousBodyLeft = body.style.left;
        const previousBodyRight = body.style.right;
        const previousBodyWidth = body.style.width;

        html.style.overflow = 'hidden';
        body.style.overflow = 'hidden';
        body.style.position = 'fixed';
        body.style.top = `-${scrollY}px`;
        body.style.left = '0';
        body.style.right = '0';
        body.style.width = '100%';

        const lockedHtmlOverflow = html.style.overflow;
        const lockedBodyOverflow = body.style.overflow;
        const lockedBodyPosition = body.style.position;
        const lockedBodyTop = body.style.top;
        const lockedBodyLeft = body.style.left;
        const lockedBodyRight = body.style.right;
        const lockedBodyWidth = body.style.width;

        return () => {
            if (html.style.overflow === lockedHtmlOverflow) html.style.overflow = previousHtmlOverflow;
            if (body.style.overflow === lockedBodyOverflow) body.style.overflow = previousBodyOverflow;
            if (body.style.position === lockedBodyPosition) body.style.position = previousBodyPosition;
            if (body.style.top === lockedBodyTop) body.style.top = previousBodyTop;
            if (body.style.left === lockedBodyLeft) body.style.left = previousBodyLeft;
            if (body.style.right === lockedBodyRight) body.style.right = previousBodyRight;
            if (body.style.width === lockedBodyWidth) body.style.width = previousBodyWidth;

            if (window.location.pathname === lockedPathname) {
                window.scrollTo(0, scrollY);
            }
        };
    }, []);

    if (!mounted) return null;

    return createPortal(
        <div
            className="viewportOverlayRoot z-[2147483647] isolate flex items-center justify-center p-4"
            data-popup-overlay-root
            style={{
                paddingTop: 'max(1rem, env(safe-area-inset-top))',
                paddingRight: 'max(1rem, env(safe-area-inset-right))',
                paddingBottom: 'max(1rem, env(safe-area-inset-bottom))',
                paddingLeft: 'max(1rem, env(safe-area-inset-left))',
                ...viewportStyle,
            }}
            onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
        >
            {/* Frosted glass backdrop */}
            <div
                className={`absolute inset-0 ${backdropClassName}`}
                data-popup-backdrop
                onClick={handleClose}
            />

            {/* Panel */}
            <div
                ref={panelRef}
                className={`animate-popup-in relative z-10 w-full rounded-[19px] max-h-[90vh] overflow-y-auto scrollbar-hide flex flex-col ${panelClassName ?? "bg-[#f3f3f3]"}`}
                style={{ maxWidth }}
            >
                {/* Close button */}
                {showClose && (
                    <button
                        onClick={handleClose}
                        className="absolute top-5 right-5 z-20 w-8 h-8 flex items-center justify-center rounded-full hover:bg-black/5 transition-colors text-black"
                        aria-label="Закрыть"
                    >
                        <svg width="20" height="20" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </button>
                )}

                {children}
            </div>
        </div>,
        document.body
    );
};
