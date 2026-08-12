"use client";

import { useEffect, useLayoutEffect, useSyncExternalStore } from "react";

const subscribeToDocumentBody = () => () => undefined;
const getDocumentBody = () => document.body;
const getServerDocumentBody = () => null;

export const useConstructorPageEnvironment = (isOverlayActive: boolean) => {
    const portalTarget = useSyncExternalStore(
        subscribeToDocumentBody,
        getDocumentBody,
        getServerDocumentBody,
    );

    useLayoutEffect(() => {
        const html = document.documentElement;
        const body = document.body;
        const previousHtmlTopColor = html.style.getPropertyValue("--app-top-color");
        const previousBodyTopColor = body.style.getPropertyValue("--app-top-color");
        const metaThemeColor = document.querySelector('meta[name="theme-color"]') as HTMLMetaElement | null;
        const previousMetaThemeColor = metaThemeColor?.content;
        let overlayThemeRefreshId: number | undefined;
        let overlayThemeSecondRefreshId: number | undefined;
        let overlayThemeRefreshTimer: number | undefined;

        const applyOverlayChrome = () => {
            html.dataset.constructorOverlayActive = "true";
            body.dataset.constructorOverlayActive = "true";
            html.style.setProperty("--app-top-color", "#FFFFFF");
            body.style.setProperty("--app-top-color", "#FFFFFF");
            if (metaThemeColor) metaThemeColor.content = "#FFFFFF";
        };

        if (isOverlayActive) {
            applyOverlayChrome();
            overlayThemeRefreshId = window.requestAnimationFrame(() => {
                applyOverlayChrome();
                overlayThemeSecondRefreshId = window.requestAnimationFrame(applyOverlayChrome);
            });
            overlayThemeRefreshTimer = window.setTimeout(applyOverlayChrome, 120);
        } else {
            delete html.dataset.constructorOverlayActive;
            delete body.dataset.constructorOverlayActive;
            html.style.setProperty("--app-top-color", "#FFFFFF");
            body.style.setProperty("--app-top-color", "#FFFFFF");
            if (metaThemeColor) metaThemeColor.content = "#FFFFFF";
        }

        return () => {
            if (overlayThemeRefreshId !== undefined) window.cancelAnimationFrame(overlayThemeRefreshId);
            if (overlayThemeSecondRefreshId !== undefined) window.cancelAnimationFrame(overlayThemeSecondRefreshId);
            if (overlayThemeRefreshTimer !== undefined) window.clearTimeout(overlayThemeRefreshTimer);
            delete html.dataset.constructorOverlayActive;
            delete body.dataset.constructorOverlayActive;
            if (previousHtmlTopColor) html.style.setProperty("--app-top-color", previousHtmlTopColor);
            else html.style.removeProperty("--app-top-color");
            if (previousBodyTopColor) body.style.setProperty("--app-top-color", previousBodyTopColor);
            else body.style.removeProperty("--app-top-color");
            if (previousMetaThemeColor && metaThemeColor) metaThemeColor.content = previousMetaThemeColor;
        };
    }, [isOverlayActive]);

    useEffect(() => {
        const previousBodyOverflow = document.body.style.overflow;
        const previousHtmlOverflow = document.documentElement.style.overflow;
        const previousBodyOverscroll = document.body.style.overscrollBehavior;
        const previousHtmlOverscroll = document.documentElement.style.overscrollBehavior;

        document.body.style.overflow = "hidden";
        document.documentElement.style.overflow = "hidden";
        document.body.style.overscrollBehavior = "none";
        document.documentElement.style.overscrollBehavior = "none";

        return () => {
            document.body.style.overflow = previousBodyOverflow;
            document.documentElement.style.overflow = previousHtmlOverflow;
            document.body.style.overscrollBehavior = previousBodyOverscroll;
            document.documentElement.style.overscrollBehavior = previousHtmlOverscroll;
        };
    }, []);

    return portalTarget;
};
