"use client";

import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { KonvaCanvasProps, PlacedHardware } from '@/lib/constructor/types';
import {
    CONSTRUCTOR_MAX_STAGE_SCALE as MAX_STAGE_SCALE,
    CONSTRUCTOR_MIN_STAGE_SCALE as MIN_STAGE_SCALE,
    DEFAULT_CONSTRUCTOR_MODEL_BOUNDS,
} from '@/lib/constructor/constants';
import {
    canPanStage,
    getStagePanBounds,
    getVisibleCanvasHeight,
    shouldDeferHardwareSelection,
} from '@/lib/constructor/utils/interaction';

export const useKonvaCanvasController = ({
    selectedModel,
    modelBounds = DEFAULT_CONSTRUCTOR_MODEL_BOUNDS,
    bottomInset = 0,
    placedItems,
    hardwareMap,
    selectedHardwareUid,
    onSelectHardware,
    onUpdateItem,
    getHardwareScaleLimits,
    onCanvasInteraction,
    onViewportChange,
}: KonvaCanvasProps) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const isPinchingRef = useRef(false);
    const pendingStageTouchRef = useRef<{
        pointerId: number;
        startX: number;
        startY: number;
        initialPos: { x: number; y: number };
        selectedItemUid: string | null;
        selectedItemX: number;
        selectedItemY: number;
        shouldClearSelection: boolean;
    } | null>(null);
    const pinchStateRef = useRef<{
        distance: number;
        angle: number;
        stageScale: number;
        stagePos: { x: number; y: number };
        center: { x: number; y: number };
        hardwareUid: string | null;
        hardwareScale: number;
        hardwareRotation: number;
    } | null>(null);
    const deferredHardwareSelectionRef = useRef<{
        pointerId: number;
        cancelled: boolean;
    } | null>(null);
    const [stagePos, setStagePos] = useState({ x: 0, y: 0 });
    const [stageScale, setStageScale] = useState(1);
    const [isMounted, setIsMounted] = useState(false);
    const stageScaleRef = useRef(stageScale);
    const fittedScaleRef = useRef(1);
    const [fittedScale, setFittedScale] = useState(1);
    const initialModelIdRef = useRef<string | null>(null);
    const modelBoundsRef = useRef(modelBounds);

    useEffect(() => {
        stageScaleRef.current = stageScale;
    }, [stageScale]);

    useEffect(() => {
        modelBoundsRef.current = modelBounds;
    }, [modelBounds]);

    const clampStagePos = (
        pos: { x: number; y: number },
        scale = stageScaleRef.current,
        bounds = modelBounds,
    ) => {
        const element = containerRef.current;
        if (!element) return pos;

        const { minX, maxX, minY, maxY } = getStagePanBounds({
            containerWidth: element.offsetWidth,
            containerHeight: element.offsetHeight,
            bottomInset,
            scale,
            bounds,
        });

        return {
            x: Math.min(Math.max(pos.x, minX), maxX),
            y: Math.min(Math.max(pos.y, minY), maxY),
        };
    };

    const getFittedScale = (width: number, height: number, bounds = modelBounds) => {
        const fitScale = Math.min(width / bounds.width, height / bounds.height, MAX_STAGE_SCALE);
        return Math.min(MAX_STAGE_SCALE, Math.max(MIN_STAGE_SCALE, fitScale));
    };

    const clampStageScale = (scale: number) => {
        const element = containerRef.current;
        if (!element) return Math.min(Math.max(scale, MIN_STAGE_SCALE), MAX_STAGE_SCALE);

        const minScale = Math.min(fittedScaleRef.current, MAX_STAGE_SCALE);
        return Math.min(Math.max(scale, minScale), MAX_STAGE_SCALE);
    };

    useEffect(() => {
        setIsMounted(true);
    }, []);

    useLayoutEffect(() => {
        if (!isMounted) return;

        const updateSize = (shouldResetScale = false) => {
            const element = containerRef.current;
            if (!element) return;

            const { offsetWidth, offsetHeight } = element;
            const bounds = modelBoundsRef.current;
            const visibleHeight = getVisibleCanvasHeight(offsetHeight, bottomInset);
            const nextFittedScale = getFittedScale(offsetWidth, offsetHeight, bounds);
            const wasZoomed = canPanStage(stageScaleRef.current, fittedScaleRef.current);
            const nextScale = shouldResetScale || !wasZoomed ? nextFittedScale : stageScaleRef.current;

            fittedScaleRef.current = nextFittedScale;
            setFittedScale(nextFittedScale);
            if (shouldResetScale) {
                setStageScale(nextScale);
            } else if (!wasZoomed) {
                setStageScale(nextScale);
            }
            setStagePos(clampStagePos({
                x: (offsetWidth - (bounds.x * 2 + bounds.width) * nextScale) / 2,
                y: (visibleHeight - (bounds.y * 2 + bounds.height) * nextScale) / 2,
            }, nextScale, bounds));
        };

        const modelId = selectedModel?.id || null;
        const shouldResetScale = initialModelIdRef.current !== modelId;
        initialModelIdRef.current = modelId;
        updateSize(shouldResetScale);
        const handleResize = () => updateSize(false);
        window.addEventListener("resize", handleResize);

        return () => {
            window.removeEventListener("resize", handleResize);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [bottomInset, selectedModel?.id, isMounted]);

    useEffect(() => {
        const element = containerRef.current;
        if (!element) return;

        const currentScale = stageScaleRef.current;
        const visibleHeight = getVisibleCanvasHeight(element.offsetHeight, bottomInset);
        setStagePos(clampStagePos({
            x: (element.offsetWidth - (modelBounds.x * 2 + modelBounds.width) * currentScale) / 2,
            y: (visibleHeight - (modelBounds.y * 2 + modelBounds.height) * currentScale) / 2,
        }, currentScale, modelBounds));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [bottomInset, modelBounds]);

    useEffect(() => {
        const element = containerRef.current;
        if (!element) return;

        onViewportChange?.({
            stagePos,
            stageScale,
            width: element.offsetWidth,
            height: element.offsetHeight,
        });
    }, [onViewportChange, stagePos, stageScale]);

    const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
        event.preventDefault();
        const scaleBy = event.deltaY < 0 ? 1.1 : 1 / 1.1;

        if (selectedHardwareUid) {
            const item = placedItems.find((placedItem) => placedItem.uid === selectedHardwareUid);
            const hardware = item ? hardwareMap[item.variantId] : null;
            if (item && hardware) {
                const limits = getHardwareScaleLimits?.(item, hardware) || { min: 0.25, max: 4 };
                const nextScale = Math.min(Math.max((item.scale || 1) * scaleBy, limits.min), limits.max);
                onUpdateItem(item.uid, { scale: nextScale });
            }
            return;
        }

        onCanvasInteraction?.();
        const container = containerRef.current;
        if (!container) return;

        const rect = container.getBoundingClientRect();
        const center = {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top,
        };

        setStageScale((current) => {
            const nextScale = clampStageScale(current * scaleBy);
            const contentPoint = {
                x: (center.x - stagePos.x) / current,
                y: (center.y - stagePos.y) / current,
            };
            setStagePos(clampStagePos({
                x: center.x - contentPoint.x * nextScale,
                y: center.y - contentPoint.y * nextScale,
            }, nextScale));
            return nextScale;
        });
    };

    const handleStagePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
        const target = event.target as HTMLElement;
        if (target.dataset.hardware === "true") return;
        if (isPinchingRef.current) return;

        event.preventDefault();

        const startX = event.clientX;
        const startY = event.clientY;
        const initialPos = stagePos;
        const selectedItem = selectedHardwareUid
            ? placedItems.find((item) => item.uid === selectedHardwareUid)
            : null;

        if (selectedItem) {
            pendingStageTouchRef.current = {
                pointerId: event.pointerId,
                startX,
                startY,
                initialPos,
                selectedItemUid: selectedItem.uid,
                selectedItemX: selectedItem.x,
                selectedItemY: selectedItem.y,
                shouldClearSelection: true,
            };
        } else {
            onSelectHardware(null);
            onCanvasInteraction?.();
        }

        const handleMove = (moveEvent: PointerEvent) => {
            if (isPinchingRef.current) return;
            const pendingTouch = pendingStageTouchRef.current;
            const distance = Math.hypot(moveEvent.clientX - startX, moveEvent.clientY - startY);

            if (pendingTouch?.selectedItemUid) {
                if (distance > 6) {
                    pendingTouch.shouldClearSelection = false;
                    onUpdateItem(pendingTouch.selectedItemUid, {
                        x: pendingTouch.selectedItemX + (moveEvent.clientX - startX) / stageScale,
                        y: pendingTouch.selectedItemY + (moveEvent.clientY - startY) / stageScale,
                    });
                }

                return;
            }

            if (pendingTouch && distance > 6) {
                pendingTouch.shouldClearSelection = false;
            }

            if (canPanStage(stageScaleRef.current, fittedScaleRef.current)) {
                setStagePos(clampStagePos({
                    x: initialPos.x + moveEvent.clientX - startX,
                    y: initialPos.y + moveEvent.clientY - startY,
                }));
            }
        };

        const handleUp = () => {
            const pendingTouch = pendingStageTouchRef.current;
            if (pendingTouch?.pointerId === event.pointerId && pendingTouch.shouldClearSelection && !isPinchingRef.current) {
                onSelectHardware(null);
                onCanvasInteraction?.();
            }

            if (pendingTouch?.pointerId === event.pointerId) {
                pendingStageTouchRef.current = null;
            }

            window.removeEventListener("pointermove", handleMove);
            window.removeEventListener("pointerup", handleUp);
            window.removeEventListener("pointercancel", handleUp);
        };

        window.addEventListener("pointermove", handleMove);
        window.addEventListener("pointerup", handleUp);
        window.addEventListener("pointercancel", handleUp);
    };

    const getTouchDistance = (touches: React.TouchList | TouchList) => {
        const first = touches[0];
        const second = touches[1];
        return Math.hypot(second.clientX - first.clientX, second.clientY - first.clientY);
    };

    const getTouchAngle = (touches: React.TouchList | TouchList) => {
        const first = touches[0];
        const second = touches[1];
        return Math.atan2(second.clientY - first.clientY, second.clientX - first.clientX) * 180 / Math.PI;
    };

    const getTouchCenter = (touches: React.TouchList | TouchList) => {
        const first = touches[0];
        const second = touches[1];
        const rect = containerRef.current?.getBoundingClientRect();

        return {
            x: (first.clientX + second.clientX) / 2 - (rect?.left || 0),
            y: (first.clientY + second.clientY) / 2 - (rect?.top || 0),
        };
    };

    const handleTouchStart = (event: React.TouchEvent<HTMLDivElement>) => {
        if (event.touches.length !== 2) return;

        event.preventDefault();
        isPinchingRef.current = true;
        pendingStageTouchRef.current = null;
        if (deferredHardwareSelectionRef.current) {
            deferredHardwareSelectionRef.current.cancelled = true;
        }
        const selectedItem = selectedHardwareUid
            ? placedItems.find((item) => item.uid === selectedHardwareUid)
            : null;

        if (!selectedItem) onCanvasInteraction?.();

        pinchStateRef.current = {
            distance: getTouchDistance(event.touches),
            angle: getTouchAngle(event.touches),
            stageScale,
            stagePos,
            center: getTouchCenter(event.touches),
            hardwareUid: selectedItem?.uid || null,
            hardwareScale: selectedItem?.scale || 1,
            hardwareRotation: selectedItem?.rotation || 0,
        };
    };

    const handleTouchMove = (event: React.TouchEvent<HTMLDivElement>) => {
        const pinchState = pinchStateRef.current;
        if (event.touches.length !== 2 || !pinchState) return;

        event.preventDefault();
        const ratio = getTouchDistance(event.touches) / pinchState.distance;

        if (pinchState.hardwareUid) {
            const item = placedItems.find((placedItem) => placedItem.uid === pinchState.hardwareUid);
            const hardware = item ? hardwareMap[item.variantId] : null;
            if (!item || !hardware) return;

            const limits = getHardwareScaleLimits?.(item, hardware) || { min: 0.25, max: 4 };
            const rotationDelta = getTouchAngle(event.touches) - pinchState.angle;
            onUpdateItem(item.uid, {
                scale: Math.min(Math.max(pinchState.hardwareScale * ratio, limits.min), limits.max),
                rotation: pinchState.hardwareRotation + rotationDelta,
            });
            return;
        }

        const nextScale = clampStageScale(pinchState.stageScale * ratio);
        const currentCenter = getTouchCenter(event.touches);
        const contentPoint = {
            x: (pinchState.center.x - pinchState.stagePos.x) / pinchState.stageScale,
            y: (pinchState.center.y - pinchState.stagePos.y) / pinchState.stageScale,
        };

        setStageScale(nextScale);
        setStagePos(clampStagePos({
            x: currentCenter.x - contentPoint.x * nextScale,
            y: currentCenter.y - contentPoint.y * nextScale,
        }, nextScale));
    };

    const handleTouchEnd = () => {
        isPinchingRef.current = false;
        pinchStateRef.current = null;
        pendingStageTouchRef.current = null;
    };

    const handleHardwarePointerDown = (event: React.PointerEvent<HTMLElement>, item: PlacedHardware) => {
        event.preventDefault();
        event.stopPropagation();

        if (shouldDeferHardwareSelection(selectedHardwareUid, item.uid)) {
            const pendingSelection = {
                pointerId: event.pointerId,
                cancelled: false,
            };
            const startX = event.clientX;
            const startY = event.clientY;
            deferredHardwareSelectionRef.current = pendingSelection;

            const handleMove = (moveEvent: PointerEvent) => {
                if (Math.hypot(moveEvent.clientX - startX, moveEvent.clientY - startY) > 6) {
                    pendingSelection.cancelled = true;
                }
            };

            const handleUp = (upEvent: PointerEvent) => {
                if (
                    upEvent.pointerId === pendingSelection.pointerId
                    && !pendingSelection.cancelled
                    && !isPinchingRef.current
                ) {
                    onSelectHardware(item.uid);
                }

                if (deferredHardwareSelectionRef.current === pendingSelection) {
                    deferredHardwareSelectionRef.current = null;
                }
                window.removeEventListener("pointermove", handleMove);
                window.removeEventListener("pointerup", handleUp);
                window.removeEventListener("pointercancel", handleUp);
            };

            window.addEventListener("pointermove", handleMove);
            window.addEventListener("pointerup", handleUp);
            window.addEventListener("pointercancel", handleUp);
            return;
        }

        onSelectHardware(item.uid);

        const startX = event.clientX;
        const startY = event.clientY;
        const initialX = item.x;
        const initialY = item.y;

        const handleMove = (moveEvent: PointerEvent) => {
            if (isPinchingRef.current) return;
            onUpdateItem(item.uid, {
                x: initialX + (moveEvent.clientX - startX) / stageScale,
                y: initialY + (moveEvent.clientY - startY) / stageScale,
            });
        };

        const handleUp = () => {
            window.removeEventListener("pointermove", handleMove);
            window.removeEventListener("pointerup", handleUp);
            window.removeEventListener("pointercancel", handleUp);
        };

        window.addEventListener("pointermove", handleMove);
        window.addEventListener("pointerup", handleUp);
        window.addEventListener("pointercancel", handleUp);
    };

    const handleRotatePointerDown = (event: React.PointerEvent<HTMLButtonElement>, item: PlacedHardware) => {
        event.preventDefault();
        event.stopPropagation();
        onSelectHardware(item.uid);

        const containerRect = containerRef.current?.getBoundingClientRect();
        if (!containerRect) return;

        const centerX = containerRect.left + stagePos.x + item.x * stageScale;
        const centerY = containerRect.top + stagePos.y + item.y * stageScale;
        const initialAngle = Math.atan2(event.clientY - centerY, event.clientX - centerX) * 180 / Math.PI;
        const initialRotation = item.rotation || 0;

        const handleMove = (moveEvent: PointerEvent) => {
            const nextAngle = Math.atan2(moveEvent.clientY - centerY, moveEvent.clientX - centerX) * 180 / Math.PI;
            onUpdateItem(item.uid, { rotation: initialRotation + nextAngle - initialAngle });
        };

        const handleUp = () => {
            window.removeEventListener("pointermove", handleMove);
            window.removeEventListener("pointerup", handleUp);
        };

        window.addEventListener("pointermove", handleMove);
        window.addEventListener("pointerup", handleUp);
    };

    return {
        containerRef,
        isMounted,
        stagePos,
        stageScale,
        isStagePannable: canPanStage(stageScale, fittedScale),
        handleWheel,
        handleStagePointerDown,
        handleTouchStart,
        handleTouchMove,
        handleTouchEnd,
        handleHardwarePointerDown,
        handleRotatePointerDown,
    };
};
