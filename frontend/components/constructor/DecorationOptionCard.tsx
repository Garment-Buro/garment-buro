"use client";

import Image from "next/image";

import type { HardwareVariant } from "@/lib/constructor/types";

type DecorationCardVariant = "rail" | "grid";

type DecorationOptionCardProps = {
    decoration: HardwareVariant;
    priceLabel: string;
    variant: DecorationCardVariant;
    captionsVisible?: boolean;
    onSelect: (decorationId: string) => void;
};

type UploadDecorationCardProps = {
    variant: DecorationCardVariant;
    captionsVisible?: boolean;
    onUpload: () => void;
};

const getCaptionTransition = (variant: DecorationCardVariant, captionsVisible: boolean) => (
    variant === "grid"
        ? ""
        : `transition-all duration-500 ease-out ${captionsVisible ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0"}`
);

export function DecorationOptionCard({
    decoration,
    priceLabel,
    variant,
    captionsVisible = true,
    onSelect,
}: DecorationOptionCardProps) {
    const captionTransition = getCaptionTransition(variant, captionsVisible);

    return (
        <button
            type="button"
            onClick={() => onSelect(decoration.id)}
            className="flex w-[50px] shrink-0 flex-col items-center text-center transition active:scale-95"
        >
            <span className="block h-[50px] w-[50px] overflow-hidden bg-transparent">
                <Image
                    src={decoration.src}
                    alt={decoration.name}
                    width={50}
                    height={50}
                    unoptimized
                    className="h-full w-full object-cover"
                />
            </span>
            <span
                className={`mt-0 block w-[50px] truncate text-center font-manrope text-[10px] font-semibold leading-[150%] tracking-[-0.4px] text-[#505050] ${captionTransition}`}
                title={decoration.name}
            >
                {decoration.name}
            </span>
            <span className={`text-center font-manrope text-[8px] font-medium leading-[150%] tracking-[-0.32px] text-[#C1C1C1] ${captionTransition}`}>
                {priceLabel}
            </span>
        </button>
    );
}

export function UploadDecorationCard({
    variant,
    captionsVisible = true,
    onUpload,
}: UploadDecorationCardProps) {
    const captionTransition = getCaptionTransition(variant, captionsVisible);

    return (
        <button
            type="button"
            onClick={onUpload}
            className="flex w-[50px] shrink-0 flex-col items-center text-center transition active:scale-95"
            aria-label="Загрузить свое украшение"
        >
            <span className="flex h-[50px] w-[50px] items-center justify-center rounded-[5px] bg-white font-manrope text-[36px] font-extralight leading-[11.582px] text-black shadow-[0_1px_1.4px_0_rgba(0,0,0,0.25)_inset]">
                +
            </span>
            <span className={`mt-0 block w-[50px] truncate text-center font-manrope text-[10px] font-semibold leading-[150%] tracking-[-0.4px] text-[#505050] ${captionTransition}`}>
                добавить
            </span>
            <span className={`text-center font-manrope text-[8px] font-medium leading-[150%] tracking-[-0.32px] text-[#C1C1C1] ${captionTransition}`}>
                &nbsp;
            </span>
        </button>
    );
}
