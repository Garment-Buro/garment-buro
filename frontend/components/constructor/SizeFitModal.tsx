"use client";

import type { CSSProperties } from "react";
import { useState } from "react";
import Image from "next/image";
import { Navigation } from "swiper/modules";
import { Swiper, SwiperSlide } from "swiper/react";

import { FitSlider } from "@/components/constructor/FitSlider";
import { CONSTRUCTOR_OVERLAY_VIEWPORT_STYLE, SIZE_MODAL_MODEL_HEIGHT_CM } from "@/lib/constructor/constants";
import type { GarmentFit, SleeveMode } from "@/lib/constructor/types";
import {
    createDefaultFit,
    getFitRangeForSize,
    getProductDimensions,
    getProductSizeOptions,
    versionConstructorMedia,
} from "@/lib/constructor/utils/constructor";
import type { ProductData } from "@/lib/products/types";
import "swiper/css";
import "swiper/css/navigation";

type SizeFitModalProps = {
    product: ProductData | null;
    selectedSize: string;
    selectedFit: GarmentFit | null;
    productImageSrc: string | null;
    onSave: (fit: GarmentFit) => void;
    onClose: () => void;
};

export function SizeFitModal({
    product,
    selectedSize,
    selectedFit,
    productImageSrc,
    onSave,
    onClose,
}: SizeFitModalProps) {
    const sizeOptions = getProductSizeOptions(product);
    const initialSize = selectedFit?.selectedSize || selectedSize || sizeOptions[0]?.size || "M";
    const [draftFit, setDraftFit] = useState<GarmentFit>(() => (
        selectedFit?.selectedSize === initialSize
            ? selectedFit
            : createDefaultFit(initialSize, getProductDimensions(product, initialSize))
    ));
    const imageSrc = productImageSrc
        || versionConstructorMedia(product?.mobile_card_image || product?.image_left)
        || "/mock/hoodie.webp";
    const standardFit = createDefaultFit(draftFit.selectedSize, getProductDimensions(product, draftFit.selectedSize));
    const standardSleeveLength = getFitRangeForSize(draftFit.selectedSize).length.defaultValue;

    const handleSelectSize = (size: string) => {
        const nextFit = createDefaultFit(size, getProductDimensions(product, size));
        setDraftFit({ ...nextFit, sleeveMode: draftFit.sleeveMode });
    };

    const handleReset = () => {
        setDraftFit(createDefaultFit(draftFit.selectedSize, getProductDimensions(product, draftFit.selectedSize)));
    };

    return (
        <div
            className="viewportOverlayRoot z-[2147483645] flex items-center justify-center bg-black/50 p-[5px]"
            style={CONSTRUCTOR_OVERLAY_VIEWPORT_STYLE}
            onClick={onClose}
        >
            <div
                className="constructorSizeModal relative flex w-full flex-col overflow-hidden rounded-[15px] bg-white p-[15px] font-manrope shadow-[0_4px_16.8px_-1px_rgba(0,0,0,0.25)]"
                onClick={(event) => event.stopPropagation()}
            >
                <div className="flex items-start justify-between">
                    <h2 className="p-[10px] text-[13px] font-medium leading-[150%] text-black [leading-trim:both] [text-edge:cap]">Настройка посадки</h2>
                    <button
                        type="button"
                        onClick={onClose}
                        className="flex h-[15px] w-[15px] items-center justify-center text-[#787878] transition active:scale-95"
                        aria-label="Закрыть настройку посадки"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden="true">
                            <path d="M0.5 0.5L12.5 12.5" stroke="currentColor" strokeLinecap="round" />
                            <path d="M12.5 0.5L0.5 12.5" stroke="currentColor" strokeLinecap="round" />
                        </svg>
                    </button>
                </div>

                <div className="relative mt-[5px] h-[clamp(210px,32dvh,300px)] shrink-0 overflow-hidden">
                    <Swiper
                        modules={[Navigation]}
                        navigation
                        style={{ "--swiper-navigation-color": "#717171", "--swiper-navigation-size": "16px" } as CSSProperties}
                        className="size-fit-swiper h-full w-full"
                    >
                        <SwiperSlide>
                            <span className="sr-only">Фото товара</span>
                            <div className="relative h-full w-full">
                                <div className="absolute left-0 top-[20px] pl-[10px] text-[8px] font-medium leading-normal text-[#B8B8B8] [leading-trim:both] [text-edge:cap]">
                                    <p>На Алексее размер {draftFit.selectedSize}</p>
                                    <p>Рост {SIZE_MODAL_MODEL_HEIGHT_CM}</p>
                                </div>
                                <div className="flex h-full w-full justify-center pl-[20px]">
                                    <Image
                                        src={imageSrc}
                                        alt={product?.title || "Фото товара"}
                                        width={290}
                                        height={245}
                                        unoptimized
                                        className="h-full w-auto max-w-full object-contain"
                                    />
                                </div>
                                <div className="absolute bottom-0 left-0 pl-[10px] text-[8px] font-medium leading-[150%] text-[#B8B8B8] [leading-trim:both] [text-edge:cap]">
                                    <div className="flex flex-col">
                                        <span>Длина: {standardFit.lengthCm}</span>
                                        <span>Ширина: {standardFit.widthCm}</span>
                                    </div>
                                    <p className="mt-[15px] whitespace-nowrap">
                                        Рукава:<br />
                                        {draftFit.sleeveMode === "standard"
                                            ? `стандартные ${draftFit.selectedSize}(${standardSleeveLength})`
                                            : `под рост ${draftFit.lengthCm}`}
                                    </p>
                                </div>
                            </div>
                        </SwiperSlide>

                        <SwiperSlide>
                            <span className="sr-only">Схема замеров</span>
                            <div className="flex h-full w-full items-center justify-center">
                                <Image src="/match_size.svg" alt="Схема замеров" width={290} height={245} className="h-full w-auto max-w-full object-contain" />
                            </div>
                        </SwiperSlide>
                    </Swiper>
                </div>

                <div className="mt-[clamp(15px,2.5dvh,25px)] flex items-center justify-center gap-[15px]">
                    {sizeOptions.map(({ size, stock }) => {
                        const isActive = draftFit.selectedSize === size;
                        return (
                            <button
                                key={size}
                                type="button"
                                disabled={stock === 0}
                                onClick={() => stock !== 0 && handleSelectSize(size)}
                                className={`flex h-[30px] w-[38px] items-center justify-center rounded-[5px] bg-white p-0 text-[18px] font-light leading-normal tracking-[-0.36px] transition [leading-trim:both] [text-edge:cap] ${stock === 0 ? "cursor-not-allowed text-[#B6B6B6]" : "text-black"}`}
                                style={isActive ? {
                                    boxShadow: "0 2px 4px 0 rgba(0, 0, 0, 0.25) inset",
                                    borderRadius: "4px",
                                } : {}}
                            >
                                {isActive ? `${size}*` : size}
                            </button>
                        );
                    })}
                </div>

                <div className="mt-[clamp(12px,2dvh,20px)] grid w-full grid-cols-[minmax(70px,85px)_minmax(0,238.017px)] items-center justify-around gap-x-[5px] font-manrope">
                    <span className="min-w-0 text-[10px] font-medium leading-[150%] text-[#686868] [leading-trim:both] [text-edge:cap]">Рукава</span>
                    <div className="flex min-w-0 items-center gap-[7px]">
                        <div className="flex h-[30px] min-w-0 w-[220px] flex-1 rounded-[5px] bg-white p-[4px] shadow-[0_0.934px_1.681px_0_rgba(0,0,0,0.26)]">
                            {([[
                                "standard", "стандартные",
                            ], ["height", "под рост"]] as Array<[SleeveMode, string]>).map(([mode, label]) => (
                                <button
                                    key={mode}
                                    type="button"
                                    onClick={() => setDraftFit((current) => ({ ...current, sleeveMode: mode }))}
                                    className={`flex flex-1 items-center justify-center rounded-[5px] text-center text-[10px] font-medium leading-[150%] transition [leading-trim:both] [text-edge:cap] ${draftFit.sleeveMode === mode ? "bg-white text-[#686868] shadow-[0_0.934px_1.308px_0_rgba(0,0,0,0.25)_inset]" : "text-[#B8B8B8]"}`}
                                >
                                    {label}
                                </button>
                            ))}
                        </div>
                        <Image src="/alert.svg" alt="" aria-hidden="true" width={11} height={8} className="h-[8px] w-[11px] shrink-0" />
                    </div>
                    <p className="col-start-2 mt-[7px] text-[8px] font-medium leading-[150%] text-[#B8B8B8] [leading-trim:both] [text-edge:cap]">
                        {draftFit.sleeveMode === "standard"
                            ? `Соответствуют размеру ${draftFit.selectedSize} - рост ${standardSleeveLength}`
                            : "Рукава подстраиваются под выбранную длину изделия"}
                    </p>
                </div>

                <div className="mt-[clamp(20px,3dvh,35px)] flex flex-col gap-[clamp(20px,3dvh,35px)]">
                    <FitSlider
                        label="Длина"
                        helper="Соответствует росту:"
                        value={draftFit.lengthCm}
                        range={getFitRangeForSize(draftFit.selectedSize).length}
                        tickStep={4}
                        onChange={(value) => setDraftFit((current) => ({ ...current, lengthCm: value }))}
                    />
                    <FitSlider
                        label="Ширина"
                        value={draftFit.widthCm}
                        range={getFitRangeForSize(draftFit.selectedSize).width}
                        tickStep={2}
                        onChange={(value) => setDraftFit((current) => ({ ...current, widthCm: value }))}
                    />
                </div>

                <div className="mt-[clamp(20px,3.5dvh,40px)] flex items-center justify-center gap-[5px]">
                    <button
                        type="button"
                        onClick={handleReset}
                        className="flex h-[30px] min-w-0 max-w-[150px] flex-1 items-center justify-center rounded-[5px] bg-white text-center text-[14px] font-semibold leading-[11.582px] text-[#C4C4C4] underline decoration-[8%] underline-offset-[20%] shadow-none transition [leading-trim:both] [text-decoration-skip-ink:auto] [text-decoration-style:solid] [text-edge:cap] [text-underline-position:from-font] active:scale-95"
                    >
                        СБРОСИТЬ
                    </button>
                    <button
                        type="button"
                        onClick={() => onSave(draftFit)}
                        className="flex h-[30px] min-w-0 max-w-[150px] flex-1 items-center justify-center rounded-[5px] bg-white text-center text-[14px] font-semibold leading-[11.582px] text-[#676767] shadow-[0_0.934px_1.681px_0_rgba(0,0,0,0.26)] transition [leading-trim:both] [text-edge:cap] active:scale-95"
                    >
                        СОХРАНИТЬ
                    </button>
                </div>
            </div>
        </div>
    );
}
