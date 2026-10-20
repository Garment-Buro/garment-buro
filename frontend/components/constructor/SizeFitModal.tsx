"use client";

import type { CSSProperties } from "react";
import { useState } from "react";
import Image from "next/image";
import { Navigation } from "swiper/modules";
import { Swiper, SwiperSlide } from "swiper/react";

import { FitSlider } from "@/components/constructor/FitSlider";
import { CONSTRUCTOR_OVERLAY_VIEWPORT_STYLE } from "@/lib/constructor/constants";
import type { GarmentFit, SleeveMode } from "@/lib/constructor/types";
import {
    createDefaultFit,
    getFitRangeForSize,
    getProductDimensions,
    getProductSizeOptions,
    getProductImageList,
    versionConstructorMedia,
} from "@/lib/constructor/utils/constructor";
import type { ConstructorProduct } from "@/lib/constructor/product";
import { constructorColorOptions, constructorSelectionStock, constructorVariantImages, selectConstructorSize } from '@/lib/constructor/selection';
import "swiper/css";
import "swiper/css/navigation";

type SizeFitModalProps = {
    product: ConstructorProduct | null;
    selectedSize: string;
    selectedColor: string | null;
    selectedFit: GarmentFit | null;
    productImageSrc: string | null;
    onSave: (fit: GarmentFit, color: string | null) => void;
    onClose: () => void;
};

export function SizeFitModal({
    product,
    selectedSize,
    selectedColor,
    selectedFit,
    productImageSrc,
    onSave,
    onClose,
}: SizeFitModalProps) {
    const sizeOptions = getProductSizeOptions(product);
    const initialSize = selectedFit?.selectedSize ?? selectedSize;
    const [draftColor, setDraftColor] = useState(selectedColor);
    const [draftFit, setDraftFit] = useState<GarmentFit>(() => (
        selectedFit?.selectedSize === initialSize
            ? selectedFit
            : createDefaultFit(initialSize, getProductDimensions(product, initialSize, selectedColor))
    ));
    const colors = constructorColorOptions(product, draftFit.selectedSize);
    const selectionAvailable = constructorSelectionStock(product, { size: draftFit.selectedSize, color: draftColor }) > 0;
    const imageSrc = versionConstructorMedia(constructorVariantImages(product, { size: draftFit.selectedSize, color: draftColor })[0]) || productImageSrc
        || versionConstructorMedia(getProductImageList(product)[0])
        || "/mock/hoodie.webp";
    const standardDimensions = getProductDimensions(product, draftFit.selectedSize, draftColor);

    const handleSelectSize = (size: string) => {
        const selection = selectConstructorSize(product, size, draftColor);
        setDraftColor(selection.color);
        const nextFit = createDefaultFit(size, getProductDimensions(product, size, selection.color));
        setDraftFit({ ...nextFit, sleeveMode: draftFit.sleeveMode });
    };

    const handleReset = () => {
        setDraftFit(createDefaultFit(draftFit.selectedSize, getProductDimensions(product, draftFit.selectedSize, draftColor)));
    };

    return (
        <div
            className="viewportOverlayRoot z-[2147483645] flex items-center justify-center bg-black/50 p-[5px]"
            style={CONSTRUCTOR_OVERLAY_VIEWPORT_STYLE}
            onClick={onClose}
        >
            <div
                className="constructorSizeModal relative flex max-h-[calc(100dvh-10px)] w-full flex-col overflow-y-auto overscroll-contain rounded-[15px] bg-white p-[15px] font-manrope shadow-[0_4px_16.8px_-1px_rgba(0,0,0,0.25)]"
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
                                    <p>Размер {draftFit.selectedSize || 'Единый'}</p>
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
                                        <span>Длина изделия: {standardDimensions.heightCm} см</span>
                                        <span>Ширина изделия: {standardDimensions.widthCm} см</span>
                                    </div>
                                    <p className="mt-[15px] whitespace-nowrap">
                                        Рукава:<br />
                                        {draftFit.sleeveMode === "standard"
                                            ? `стандартные ${draftFit.selectedSize || 'Единый'}`
                                            : `под рост ${draftFit.lengthCm} см`}
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

                <div className="mt-[clamp(15px,2.5dvh,25px)] flex flex-wrap items-center justify-center gap-[15px]" role="group" aria-label="Размер товара">
                    {sizeOptions.map(({ size, stock }) => {
                        const isActive = draftFit.selectedSize === size;
                        return (
                            <button
                                key={size}
                                type="button"
                                disabled={stock === 0}
                                aria-pressed={isActive}
                                onClick={() => stock !== 0 && handleSelectSize(size)}
                                className={`flex h-[30px] min-w-[38px] items-center justify-center rounded-[5px] bg-white px-2 text-[18px] font-light leading-normal tracking-[-0.36px] transition [leading-trim:both] [text-edge:cap] ${stock === 0 ? "cursor-not-allowed text-[#B6B6B6]" : "text-black"}`}
                                style={isActive ? {
                                    boxShadow: "0 2px 4px 0 rgba(0, 0, 0, 0.25) inset",
                                    borderRadius: "4px",
                                } : {}}
                            >
                                {isActive ? `${size || 'Единый'}*` : size || 'Единый'}
                            </button>
                        );
                    })}
                </div>

                {colors.length > 0 && <label className="mt-3 flex items-center justify-center gap-3 text-sm">
                    Цвет
                    <select aria-label="Цвет товара" value={colors.findIndex(option => option.color === draftColor)} onChange={event => setDraftColor(colors[Number(event.target.value)]?.color ?? null)} className="min-w-0 max-w-full rounded border px-2 py-1">
                        {!colors.some(option => option.color === draftColor) && <option value={-1} disabled>Выберите цвет</option>}
                        {colors.map((option, index) => <option key={option.color} value={index} disabled={option.stock === 0}>{option.color || 'Без цвета'}{option.stock === 0 ? ' — нет в наличии' : ''}</option>)}
                    </select>
                </label>}
                {!selectionAvailable && <p role="status" className="mt-2 text-center text-sm text-[#686868]">Выберите доступный размер и цвет товара.</p>}

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
                            ? `Соответствуют размеру ${draftFit.selectedSize || 'Единый'}`
                            : "Пожелание по рукавам для выбранного роста"}
                    </p>
                </div>

                <div className="mt-[clamp(20px,3dvh,35px)] flex flex-col gap-[clamp(20px,3dvh,35px)]">
                    <FitSlider
                        label="Рост, см"
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
                        onClick={() => onSave(draftFit, draftColor)}
                        disabled={!selectionAvailable}
                        className="flex h-[30px] min-w-0 max-w-[150px] flex-1 items-center justify-center rounded-[5px] bg-white text-center text-[14px] font-semibold leading-[11.582px] text-[#676767] shadow-[0_0.934px_1.681px_0_rgba(0,0,0,0.26)] transition [leading-trim:both] [text-edge:cap] active:scale-95"
                    >
                        СОХРАНИТЬ
                    </button>
                </div>
            </div>
        </div>
    );
}
