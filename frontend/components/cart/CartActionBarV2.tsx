"use client";

import { useEffect, useState } from "react";

import type { CartActionBarProps } from "@/lib/cart/actionTypes";

import { CartActionBar } from "./CartActionBar";

const SHIFT_TRIGGER_BOTTOM_OFFSET = 64;

export type CartActionBarV2Props = Omit<
    CartActionBarProps,
    "visible" | "allowEmptyExpand" | "collapsedVariant" | "liquidV2Shifted"
> & {
    shiftAfterElementId?: string;
};

export function CartActionBarV2({
    shiftAfterElementId,
    ...props
}: CartActionBarV2Props) {
    const [hasPassedShiftTrigger, setHasPassedShiftTrigger] = useState(false);

    useEffect(() => {
        let animationFrame = 0;

        const updateShiftTrigger = () => {
            animationFrame = 0;
            const triggerElement = shiftAfterElementId
                ? document.getElementById(shiftAfterElementId)
                : null;

            if (triggerElement) {
                setHasPassedShiftTrigger(
                    triggerElement.getBoundingClientRect().bottom
                        <= window.innerHeight - SHIFT_TRIGGER_BOTTOM_OFFSET,
                );
                return;
            }

            const pageHeight = document.documentElement.scrollHeight;
            const viewportBottom = window.scrollY + window.innerHeight;
            setHasPassedShiftTrigger(viewportBottom >= pageHeight - 2);
        };

        const scheduleUpdate = () => {
            if (animationFrame) return;
            animationFrame = window.requestAnimationFrame(updateShiftTrigger);
        };

        const resizeObserver = new ResizeObserver(scheduleUpdate);
        resizeObserver.observe(document.documentElement);
        window.addEventListener("scroll", scheduleUpdate, { passive: true });
        window.addEventListener("resize", scheduleUpdate);
        updateShiftTrigger();

        return () => {
            resizeObserver.disconnect();
            window.removeEventListener("scroll", scheduleUpdate);
            window.removeEventListener("resize", scheduleUpdate);
            if (animationFrame) window.cancelAnimationFrame(animationFrame);
        };
    }, [shiftAfterElementId]);

    return (
        <CartActionBar
            {...props}
            visible
            allowEmptyExpand
            collapsedVariant="liquid-v2"
            liquidV2Shifted={hasPassedShiftTrigger}
        />
    );
}
