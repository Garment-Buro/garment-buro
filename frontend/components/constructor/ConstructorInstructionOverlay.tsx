"use client";

import Image from "next/image";
import { createPortal } from "react-dom";

import { CONSTRUCTOR_INSTRUCTION_OVERLAY_VIEWPORT_STYLE } from "@/lib/constructor/constants";

type ConstructorInstructionOverlayProps = {
    isOpen: boolean;
    portalTarget: HTMLElement | null;
    onDismiss: () => void;
};

export function ConstructorInstructionOverlay({
    isOpen,
    portalTarget,
    onDismiss,
}: ConstructorInstructionOverlayProps) {
    if (!isOpen) return null;

    const overlay = (
        <button
            type="button"
            aria-label="Закрыть инструкцию конструктора"
            onClick={onDismiss}
            className="viewportOverlayRoot z-[2147483646] flex cursor-pointer items-start justify-end bg-black/50 px-[15px]"
            style={CONSTRUCTOR_INSTRUCTION_OVERLAY_VIEWPORT_STYLE}
        >
            <Image
                src="/instuction.webp"
                alt=""
                aria-hidden="true"
                width={265}
                height={150}
                priority
                unoptimized
                className="relative z-10 h-[clamp(125px,40.54vw,150px)] max-h-[calc(100dvh-60px)] w-[clamp(220px,71.62vw,265px)] max-w-[calc(100vw-40px)] object-contain"
            />
        </button>
    );

    return portalTarget ? createPortal(overlay, portalTarget) : overlay;
}
