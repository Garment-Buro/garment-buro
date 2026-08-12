"use client";

import { useState } from "react";

import type { MeasurementRange } from "@/lib/constructor/types";

type FitSliderProps = {
    label: string;
    helper?: string;
    value: number;
    range: MeasurementRange;
    tickStep: number;
    onChange: (value: number) => void;
};

export function FitSlider({ label, helper, value, range, tickStep, onChange }: FitSliderProps) {
    const tickValues = Array.from(
        { length: Math.floor((range.max - range.min) / tickStep) + 1 },
        (_, index) => range.min + index * tickStep,
    ).filter((tick) => tick <= range.max);
    const markValues = Array.from(new Set([...tickValues, range.max])).sort((a, b) => a - b);
    const getPercent = (measurement: number) => (
        ((measurement - range.min) / Math.max(1, range.max - range.min)) * 100
    );
    const valuePercent = getPercent(value);
    const defaultPercent = getPercent(range.defaultValue);
    const [isInteracting, setIsInteracting] = useState(false);

    return (
        <div className="grid w-full grid-cols-[minmax(70px,85px)_minmax(0,238.017px)] items-center justify-around gap-[5px] font-manrope">
            <div className="min-w-0">
                <p className="text-[13px] font-medium leading-[150%] text-black [leading-trim:both] [text-edge:cap]">{label}</p>
                {helper ? (
                    <p className="mt-[18px] w-full whitespace-nowrap text-center text-[8px] font-medium leading-[150%] text-[#B8B8B8] [leading-trim:both] [text-edge:cap]">{helper}</p>
                ) : null}
            </div>
            <div className="min-w-0">
                <div className="relative mt-[18px] w-[238.017px] max-w-full">
                    <div className="relative h-[12px] w-[238.017px] max-w-full">
                        <div className="absolute left-0 top-1/2 w-[238.017px] max-w-full h-[2px] -translate-y-1/2 rounded-[2px] bg-[#D3D3D3]" />
                        {markValues.map((tick) => (
                            <span
                                key={`mark-${tick}`}
                                className="absolute top-1/2 w-[1.983px] h-[4px] -translate-x-1/2 -translate-y-1/2 rounded-[5px] bg-[#D9D9D9]"
                                style={{ left: `${getPercent(tick)}%` }}
                            />
                        ))}
                        <span
                            className="pointer-events-none absolute top-1/2 z-[2] h-[12px] w-[12px] -translate-x-1/2 -translate-y-1/2"
                            style={{ left: `${defaultPercent}%` }}
                            aria-hidden="true"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12" fill="none">
                                <ellipse cx="5.95041" cy="6" rx="5.95041" ry="6" fill="#D3D3D3" />
                            </svg>
                        </span>
                        <span
                            className={`pointer-events-none absolute top-1/2 z-[3] h-[16px] w-[16px] -translate-x-1/2 -translate-y-1/2 transition-transform duration-150 ${isInteracting ? "scale-[1.28]" : "scale-100"}`}
                            style={{ left: `${valuePercent}%` }}
                            aria-hidden="true"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
                                <ellipse cx="7.93257" cy="8" rx="7.93257" ry="8" fill="black" />
                            </svg>
                        </span>
                        <span
                            className={`pointer-events-none absolute top-[-23px] z-[4] -translate-x-1/2 font-manrope text-[12px] font-bold leading-[150%] text-black transition-transform duration-150 [leading-trim:both] [text-edge:cap] ${isInteracting ? "scale-[1.28]" : "scale-100"}`}
                            style={{ left: `${valuePercent}%` }}
                        >
                            {value}
                        </span>
                        <input
                            type="range"
                            min={range.min}
                            max={range.max}
                            value={value}
                            onChange={(event) => onChange(Number(event.target.value))}
                            onPointerDown={() => setIsInteracting(true)}
                            onPointerUp={() => setIsInteracting(false)}
                            onPointerCancel={() => setIsInteracting(false)}
                            onFocus={() => setIsInteracting(true)}
                            onBlur={() => setIsInteracting(false)}
                            className="absolute inset-x-[-6px] top-0 z-10 h-[12px] w-[calc(100%+12px)] cursor-pointer opacity-0"
                            aria-label={label}
                        />
                    </div>
                    <div className="relative mt-[8px] h-[12px] w-[238.017px] max-w-full font-manrope text-[8px] font-medium leading-[150%] text-[#B3B3B3] [leading-trim:both] [text-edge:cap]">
                        {markValues.map((tick) => (
                            <span
                                key={`label-${tick}`}
                                className="absolute top-0 -translate-x-1/2 font-medium text-[#B3B3B3]"
                                style={{ left: `${getPercent(tick)}%` }}
                            >
                                {tick}
                            </span>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
