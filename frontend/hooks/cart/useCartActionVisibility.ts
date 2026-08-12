"use client";

import React from 'react';

import { CART_ACTION_EXIT_MS } from '@/lib/cart/constants';

type CartActionVisibilityOptions = {
    visible: boolean;
    isExpanded: boolean;
    shouldShowCartAction: boolean;
    setIsExpanded: React.Dispatch<React.SetStateAction<boolean>>;
};

export const useCartActionVisibility = ({
    visible,
    isExpanded,
    shouldShowCartAction,
    setIsExpanded,
}: CartActionVisibilityOptions) => {
    const [isRendered, setIsRendered] = React.useState(visible);
    const [isVisibleFrame, setIsVisibleFrame] = React.useState(false);
    const [isAuthHydrated, setIsAuthHydrated] = React.useState(false);

    React.useEffect(() => {
        setIsAuthHydrated(true);
    }, []);

    React.useEffect(() => {
        let frameId: number | undefined;
        let hideTimer: number | undefined;

        if (shouldShowCartAction) {
            setIsRendered(true);
            setIsVisibleFrame(false);
            frameId = window.requestAnimationFrame(() => {
                frameId = window.requestAnimationFrame(() => setIsVisibleFrame(true));
            });
        } else {
            setIsVisibleFrame(false);
            hideTimer = window.setTimeout(() => setIsRendered(false), CART_ACTION_EXIT_MS);
        }

        return () => {
            if (frameId !== undefined) window.cancelAnimationFrame(frameId);
            if (hideTimer !== undefined) window.clearTimeout(hideTimer);
        };
    }, [shouldShowCartAction]);

    React.useEffect(() => {
        if (!visible && !isExpanded) {
            setIsExpanded(false);
        }
    }, [isExpanded, visible, setIsExpanded]);

    return {
        isRendered,
        setIsRendered,
        isVisibleFrame,
        setIsVisibleFrame,
        isAuthHydrated,
    };
};
