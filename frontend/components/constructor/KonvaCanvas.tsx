"use client";

import React from 'react';
import { RawMediaImage } from '@/components/shared/RawMediaImage';
import type { KonvaCanvasProps } from '@/lib/constructor/types';
import {
    CANVAS_SIZE,
    DEFAULT_CONSTRUCTOR_MODEL_BOUNDS,
} from '@/lib/constructor/constants';
import { useKonvaCanvasController } from '@/hooks/constructor/useKonvaCanvasController';

export const KonvaCanvas: React.FC<KonvaCanvasProps> = (props) => {
    const {
        selectedModel,
        activeImageSrc,
        modelBounds = DEFAULT_CONSTRUCTOR_MODEL_BOUNDS,
        placedItems,
        hardwareMap,
        selectedHardwareUid,
        onRemoveHardware,
    } = props;
    const {
        containerRef,
        isMounted,
        stagePos,
        stageScale,
        isStagePannable,
        handleWheel,
        handleStagePointerDown,
        handleTouchStart,
        handleTouchMove,
        handleTouchEnd,
        handleHardwarePointerDown,
        handleRotatePointerDown,
    } = useKonvaCanvasController(props);

    if (!isMounted) return <div className="h-full w-full" />;

    return (
        <div
            ref={containerRef}
            data-constructor-canvas="true"
            className={`relative h-full w-full overflow-hidden bg-transparent ${isStagePannable ? "cursor-grab active:cursor-grabbing" : "cursor-default"}`}
            style={{ touchAction: "none" }}
            onWheel={handleWheel}
            onPointerDown={handleStagePointerDown}
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleTouchEnd}
            onTouchCancel={handleTouchEnd}
        >
            <div
                className="absolute left-0 top-0 origin-top-left"
                style={{
                    width: CANVAS_SIZE,
                    height: CANVAS_SIZE,
                    transform: `translate(${stagePos.x}px, ${stagePos.y}px) scale(${stageScale})`,
                }}
            >
                {selectedModel && (
                    <RawMediaImage
                        src={activeImageSrc || selectedModel.src}
                        alt={selectedModel.name}
                        draggable={false}
                        className="pointer-events-none absolute select-none object-contain"
                        style={{
                            left: modelBounds.x,
                            top: modelBounds.y,
                            width: modelBounds.width,
                            height: modelBounds.height,
                        }}
                    />
                )}

                {placedItems.map((item) => {
                    const hardwareDef = hardwareMap[item.variantId];
                    if (!hardwareDef) return null;

                    const isSelected = item.uid === selectedHardwareUid;
                    const width = hardwareDef.defaultWidth || 50;
                    const height = hardwareDef.defaultHeight || width;
                    const itemScale = Math.max(item.scale || 1, 0.01);
                    const visualScale = Math.max(itemScale * stageScale, 0.01);
                    const selectionLineWidth = Math.max(0.5, 1 / visualScale);
                    const selectionGlowWidth = Math.max(1.5, 3 / visualScale);
                    // Constant on-screen size so the delete button stays whole and
                    // pinned to the corner instead of moving/resizing when the
                    // decoration is scaled. `/ visualScale` counters the item scale
                    // so it renders at a steady ~28px regardless of zoom.
                    const deleteButtonScreenSize = 28;
                    const controlSize = deleteButtonScreenSize / visualScale;
                    const deleteOffset = -(deleteButtonScreenSize / 2) / visualScale;
                    const deleteIconSize = (deleteButtonScreenSize * 0.46) / visualScale;
                    const rotateControlSize = 24 / visualScale;
                    const rotateOffset = -13 / visualScale;
                    const rotateIconSize = 14 / visualScale;

                    return (
                        <div
                            key={item.uid}
                            data-hardware="true"
                            onPointerDown={(event) => handleHardwarePointerDown(event, item)}
                            className={`absolute cursor-grab select-none transition-shadow active:cursor-grabbing ${isSelected
                                ? ""
                                : "hover:shadow-[0_0_0_5px_rgba(0,0,0,0.08)]"
                            }`}
                            style={{
                                left: 0,
                                top: 0,
                                width,
                                height,
                                // Position purely via `transform` (composited) instead of
                                // animating left/top, which triggers a layout reflow on every
                                // pointermove and makes slow drags jitter.
                                transform: `translate(${item.x}px, ${item.y}px) translate(-50%, -50%) rotate(${item.rotation || 0}deg) scale(${item.scale})`,
                                willChange: "transform",
                                ...(isSelected ? {
                                    outline: `${selectionLineWidth}px solid #27C9C7`,
                                    boxShadow: `0 0 0 ${selectionGlowWidth}px rgba(39, 201, 199, 0.18)`,
                                } : {}),
                            }}
                        >
                            <RawMediaImage
                                data-hardware="true"
                                src={hardwareDef.src}
                                alt={hardwareDef.name}
                                draggable={false}
                                className="pointer-events-none h-full w-full select-none object-contain"
                            />
                            {isSelected && onRemoveHardware && (
                                <>
                                <button
                                    type="button"
                                    data-hardware="true"
                                    onPointerDown={(event) => handleRotatePointerDown(event, item)}
                                    className="absolute hidden items-center justify-center rounded-full bg-white text-[#3D3D3D] shadow-[0_2px_8px_rgba(0,0,0,0.22)] transition active:opacity-80 md:flex"
                                    style={{
                                        left: rotateOffset,
                                        top: rotateOffset,
                                        width: rotateControlSize,
                                        height: rotateControlSize,
                                    }}
                                    aria-label="Повернуть украшение"
                                >
                                    <svg width={rotateIconSize} height={rotateIconSize} viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                        <path d="M19 8A7 7 0 1 0 20 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                                        <path d="M19 4V8H15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                    </svg>
                                </button>
                                <button
                                    type="button"
                                    data-hardware="true"
                                    onPointerDown={(event) => {
                                        event.preventDefault();
                                        event.stopPropagation();
                                    }}
                                    onClick={(event) => {
                                        event.preventDefault();
                                        event.stopPropagation();
                                        onRemoveHardware(item.uid);
                                    }}
                                    className="absolute flex items-center justify-center rounded-full bg-white font-semibold leading-none text-[#E02727] shadow-[0_2px_8px_rgba(0,0,0,0.22)] transition active:opacity-80"
                                    style={{
                                        right: deleteOffset,
                                        top: deleteOffset,
                                        width: controlSize,
                                        height: controlSize,
                                    }}
                                    aria-label="Удалить украшение"
                                >
                                    <svg width={deleteIconSize} height={deleteIconSize} viewBox="0 0 12 12" fill="none" aria-hidden="true">
                                        <path d="M2.25 2.25L9.75 9.75M9.75 2.25L2.25 9.75" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                                    </svg>
                                </button>
                                </>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
};
