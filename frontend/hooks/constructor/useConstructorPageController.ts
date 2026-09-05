"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { loadConstructorDraft, saveConstructorDraft } from "@/lib/unfinished/utils/savedItems";
import { useConstructorPageEnvironment } from "@/hooks/constructor/useConstructorPageEnvironment";
import { useConstructorProduct } from "@/hooks/constructor/useConstructorProduct";
import { useConstructorDerivedState } from "@/hooks/constructor/useConstructorDerivedState";
import { getNextDecorationDropPosition, getPanelSwipeAction } from "@/lib/constructor/utils/interaction";
import {
    CANVAS_SIZE,
    COLLAPSED_PANEL_BASE_HEIGHT,
    CUSTOM_BASE_PRICE,
    PX_PER_CM,
    ROTATE_CONTROLS_HEIGHT,
    ROTATE_PANEL_GAP,
} from "@/lib/constructor/constants";
import type {
    CanvasViewport,
    ConstructorPageProps,
    HardwareCategory,
    HardwareVariant,
    ModelView,
    PlacedHardware,
    PlacedItemsByView,
    TextDecoration,
    UploadedImage,
} from "@/lib/constructor/types";
import {
    buildConstructorCustomization,
    clampCanvasPoint,
    createDefaultFit,
    getCustomDecorationsFromCartItem,
    getCustomDecorationsFromCustomization,
    getFirstAvailableSize,
    getHardwareScaleLimits,
    getItemSizeCm,
    getPlacedItemsFromCartItem,
    getPlacedItemsFromCustomization,
    getProductDimensions,
    readUploadedImage,
} from "@/lib/constructor/utils/constructor";
import type { CartItem } from "@/lib/cart/types";
import { useCartStore } from "@/store/cartStore";

export const useConstructorPageController = ({
    productId: initialProductId = null,
    editCartItemId: initialEditCartItemId = null,
    draftId: initialDraftId = null,
}: ConstructorPageProps = {}) => {
    const router = useRouter();
    const [modelView, setModelView] = useState<ModelView>("front");
    const [selectedCategory, setSelectedCategory] = useState<HardwareCategory>("prints");
    const [placedItemsByView, setPlacedItemsByView] = useState<PlacedItemsByView>({ front: [], back: [] });
    const [selectedItemUid, setSelectedItemUid] = useState<string | null>(null);
    const [customDecorations, setCustomDecorations] = useState<HardwareVariant[]>([]);
    const [isTextEditorOpen, setIsTextEditorOpen] = useState(false);
    const [editingTextUid, setEditingTextUid] = useState<string | null>(null);
    const [areDecorationCaptionsVisible, setAreDecorationCaptionsVisible] = useState(false);
    const [isPanelExpanded, setIsPanelExpanded] = useState(false);
    const [isCustomizationDetailsOpen, setIsCustomizationDetailsOpen] = useState(false);
    const [isExitPopupOpen, setIsExitPopupOpen] = useState(false);
    const [comment, setComment] = useState("");
    const [isInstructionMounted, setIsInstructionMounted] = useState(!initialDraftId);
    const [restoredDraftModelImages, setRestoredDraftModelImages] = useState<Record<ModelView, string> | null>(null);
    const constructorProductId = initialProductId;
    const editCartItemId = initialEditCartItemId;
    const constructorDraftId = initialDraftId;
    const uploadInputRef = useRef<HTMLInputElement | null>(null);
    const commentInputRef = useRef<HTMLInputElement | null>(null);
    const decorationsScrollerRef = useRef<HTMLDivElement | null>(null);
    const captionsRevealTimerRef = useRef<number | null>(null);
    const panelDragStartYRef = useRef<number | null>(null);
    const panelRef = useRef<HTMLDivElement | null>(null);
    const canvasViewportRef = useRef<CanvasViewport | null>(null);
    const nextItemIdRef = useRef(0);
    const nextCustomDecorationIdRef = useRef(0);
    const loadedEditCartItemIdRef = useRef<string | null>(null);
    const loadedDraftIdRef = useRef<string | null>(null);
    const [glassRefreshId, setGlassRefreshId] = useState(0);
    const { items, activeItemId, addItem, updateItem, setIsCartOpen } = useCartStore();
    const editingCartItem = useMemo(
        () => editCartItemId ? items.find((item) => item.id === editCartItemId) : undefined,
        [editCartItemId, items],
    );
    const constructorCartItem = useMemo(() => {
        if (editCartItemId) return editingCartItem;

        const activeItem = activeItemId ? items.find((item) => item.id === activeItemId) : undefined;
        return editingCartItem || activeItem || items[items.length - 1];
    }, [activeItemId, editCartItemId, editingCartItem, items]);
    const productIdToLoad = constructorProductId || (editingCartItem?.product_id ? String(editingCartItem.product_id) : null);
    const {
        product,
        selectedSize,
        setSelectedSize,
        selectedFit,
        setSelectedFit,
        isSizeModalOpen,
        setIsSizeModalOpen,
        handleSaveFit,
    } = useConstructorProduct(productIdToLoad);
    const isConstructorOverlayActive = isInstructionMounted || isSizeModalOpen || isExitPopupOpen;
    const instructionPortalTarget = useConstructorPageEnvironment(isConstructorOverlayActive);

    useEffect(() => {
        setIsCartOpen(false);
    }, [editCartItemId, setIsCartOpen]);

    useEffect(() => {
        if (!editingCartItem || !product) return;
        if (loadedEditCartItemIdRef.current === editingCartItem.id) return;

        const editSize = editingCartItem.customization?.selectedSize || editingCartItem.size || getFirstAvailableSize(product);
        const editFit = editingCartItem.customization?.fit || createDefaultFit(editSize, getProductDimensions(product, editSize));
        const restoredPlacedItems = getPlacedItemsFromCartItem(editingCartItem);
        const restoredCustomDecorations = getCustomDecorationsFromCartItem(editingCartItem);
        const restoredDecorations = editingCartItem.customization?.decorations || [];
        const maxItemIndex = Math.max(
            0,
            ...restoredDecorations
                .map((decoration) => Number(decoration.uid.replace(/^item_/, "")))
                .filter((value) => Number.isFinite(value)),
        );
        const maxCustomDecorationIndex = Math.max(
            0,
            ...restoredCustomDecorations
                .map((decoration) => Number(decoration.id.replace(/^custom_/, "")))
                .filter((value) => Number.isFinite(value)),
        );

        const frameId = window.requestAnimationFrame(() => {
            setSelectedSize(editSize);
            setSelectedFit(editFit);
            setComment(editingCartItem.customization?.comment || "");
            setPlacedItemsByView(({
                front: restoredPlacedItems.front,
                back: restoredPlacedItems.back,
            }));
            setCustomDecorations(restoredCustomDecorations);
            setSelectedItemUid(null);
            setAreDecorationCaptionsVisible(restoredDecorations.length > 0);
            nextItemIdRef.current = maxItemIndex;
            nextCustomDecorationIdRef.current = maxCustomDecorationIndex;
            loadedEditCartItemIdRef.current = editingCartItem.id;
        });

        return () => {
            window.cancelAnimationFrame(frameId);
        };
    }, [editingCartItem, product, setSelectedFit, setSelectedSize]);

    useEffect(() => {
        if (!constructorDraftId || !product || editCartItemId) return;
        if (loadedDraftIdRef.current === constructorDraftId) return;

        const draft = loadConstructorDraft(constructorDraftId);
        const draftState = draft?.draftState;
        if (!draftState) return;

        const { customization } = draftState;
        const restoredPlacedItems = getPlacedItemsFromCustomization(customization);
        const restoredCustomDecorations = getCustomDecorationsFromCustomization(customization);
        const maxItemIndex = Math.max(
            0,
            ...customization.decorations
                .map((decoration) => Number(decoration.uid.replace(/^item_/, "")))
                .filter((value) => Number.isFinite(value)),
        );
        const maxCustomDecorationIndex = Math.max(
            0,
            ...restoredCustomDecorations
                .map((decoration) => Number(decoration.id.replace(/^custom_/, "")))
                .filter((value) => Number.isFinite(value)),
        );

        const frameId = window.requestAnimationFrame(() => {
            setSelectedSize(customization.selectedSize);
            setSelectedFit(
                customization.fit
                || createDefaultFit(customization.selectedSize, getProductDimensions(product, customization.selectedSize)),
            );
            setComment(customization.comment || "");
            setPlacedItemsByView(restoredPlacedItems);
            setCustomDecorations(restoredCustomDecorations);
            setRestoredDraftModelImages(customization.modelImages);
            setModelView(draftState.activeView);
            setSelectedItemUid(null);
            setAreDecorationCaptionsVisible(customization.decorations.length > 0);
            setIsInstructionMounted(false);
            nextItemIdRef.current = maxItemIndex;
            nextCustomDecorationIdRef.current = maxCustomDecorationIndex;
            loadedDraftIdRef.current = constructorDraftId;
        });

        return () => window.cancelAnimationFrame(frameId);
    }, [
        constructorDraftId,
        editCartItemId,
        product,
        setSelectedFit,
        setSelectedSize,
    ]);

    useEffect(() => {
        decorationsScrollerRef.current?.scrollTo({ left: 0 });
    }, [isPanelExpanded, selectedCategory]);

    useEffect(() => () => {
        if (captionsRevealTimerRef.current) {
            window.clearTimeout(captionsRevealTimerRef.current);
        }
    }, []);

    const {
        frontImage,
        backImage,
        activeImageSrc,
        displayActiveImageSrc,
        placedItems,
        garmentDimensions,
        modelBounds,
        canUploadCustomDecoration,
        selectedModel,
        currentVariants,
        hardwareMap,
        customizationPrice,
        totalPrice,
        placedItemDetails,
        decorationPages,
        getDecorationPanelPrice,
    } = useConstructorDerivedState({
        product,
        selectedSize,
        modelView,
        selectedCategory,
        customDecorations,
        placedItemsByView,
        selectedItemUid,
        restoredModelImages: restoredDraftModelImages,
    });

    const toggleModelView = () => {
        setModelView((current) => (current === "front" ? "back" : "front"));
        setSelectedItemUid(null);
        setGlassRefreshId((value) => value + 1);
    };

    const handleCanvasInteraction = () => {
        setAreDecorationCaptionsVisible(false);
        setGlassRefreshId((value) => value + 1);
    };

    const revealDecorationCaptionsFromScroll = () => {
        if (isPanelExpanded || areDecorationCaptionsVisible || captionsRevealTimerRef.current) return;

        captionsRevealTimerRef.current = window.setTimeout(() => {
            setAreDecorationCaptionsVisible(true);
            captionsRevealTimerRef.current = null;
        }, 120);
    };

    const collapsedPanelHeight = areDecorationCaptionsVisible ? 202 : 178;
    const expandedPanelHeight = 500;
    const panelHeight = isPanelExpanded ? expandedPanelHeight : collapsedPanelHeight;
    const panelBottom = "var(--constructor-panel-bottom, 5px)";
    const panelBottomForCanvas = 10;

    const handleAddHardware = (variantId: string, newHardware?: HardwareVariant) => {
        setAreDecorationCaptionsVisible(true);
        setGlassRefreshId((value) => value + 1);
        const hardware = newHardware || hardwareMap[variantId];
        const baseSize = hardware
            ? getItemSizeCm({ uid: "", variantId, x: 0, y: 0, scale: 1 }, hardware)
            : null;
        const viewport = canvasViewportRef.current;
        // Drop the new decoration slightly above the centre of the area that
        // remains visible above the decorations panel (even when it is fully
        // expanded), so it is always on screen right after being added.
        const visibleAreaHeight = viewport
            ? Math.max(120, viewport.height - (panelHeight + panelBottomForCanvas))
            : CANVAS_SIZE;
        const targetScreenY = viewport ? visibleAreaHeight / 2 : CANVAS_SIZE * 0.42;
        const centerPoint = viewport
            ? {
                x: clampCanvasPoint((viewport.width / 2 - viewport.stagePos.x) / viewport.stageScale),
                y: clampCanvasPoint((targetScreenY - viewport.stagePos.y) / viewport.stageScale),
            }
            : { x: CANVAS_SIZE / 2, y: CANVAS_SIZE * 0.42 };
        nextItemIdRef.current += 1;
        const newItemUid = `item_${nextItemIdRef.current}`;
        setPlacedItemsByView((prev) => ({
            ...prev,
            [modelView]: [
                ...prev[modelView],
                {
                    uid: newItemUid,
                    variantId,
                    ...getNextDecorationDropPosition({
                        centerPoint,
                        existingItems: prev[modelView],
                        canvasSize: CANVAS_SIZE,
                    }),
                    scale: hardware?.text ? Math.min(1, 300 / Math.max(hardware.defaultWidth, hardware.defaultHeight || 1)) : 1,
                    rotation: 0,
                    ...(baseSize ? { baseLongSideCm: baseSize.longSideCm } : {}),
                },
            ],
        }));
        setSelectedItemUid(newItemUid);
    };

    const selectedTextItem = placedItems.find((item) => item.uid === selectedItemUid && hardwareMap[item.variantId]?.text);
    const editingTextItem = placedItems.find((item) => item.uid === editingTextUid);
    const openTextEditor = (uid: string | null = null) => {
        setIsInstructionMounted(false);
        setEditingTextUid(uid);
        setIsTextEditorOpen(true);
    };
    const saveTextDecoration = (result: UploadedImage & { text: TextDecoration }) => {
        nextCustomDecorationIdRef.current += 1;
        const variant: HardwareVariant = {
            id: `custom_${nextCustomDecorationIdRef.current}`,
            categoryId: 'prints',
            name: result.text.content,
            src: result.src,
            text: result.text,
            defaultWidth: result.width,
            defaultHeight: result.height,
            price: CUSTOM_BASE_PRICE,
            basePrice: CUSTOM_BASE_PRICE,
            minSizeMm: 10,
            maxSizeMm: 600,
            isCustom: true,
        };
        const oldVariantStillUsed = editingTextItem && Object.values(placedItemsByView).flat().some((item) => (
            item.uid !== editingTextItem.uid && item.variantId === editingTextItem.variantId
        ));
        setCustomDecorations((previous) => [
            ...previous.filter((entry) => !editingTextItem || oldVariantStillUsed || entry.id !== editingTextItem.variantId),
            variant,
        ]);
        if (editingTextItem) {
            setPlacedItemsByView((previous) => ({
                ...previous,
                [modelView]: previous[modelView].map((item) => item.uid === editingTextItem.uid
                    ? { ...item, variantId: variant.id, baseLongSideCm: Math.max(result.width, result.height) / PX_PER_CM }
                    : item),
            }));
        } else {
            handleAddHardware(variant.id, variant);
        }
        setSelectedCategory('prints');
    };

    const handleUpdateItem = (uid: string, newAttrs: Partial<PlacedHardware>) => {
        setPlacedItemsByView((prev) => ({
            ...prev,
            [modelView]: prev[modelView].map((item) => (item.uid === uid ? { ...item, ...newAttrs } : item)),
        }));
    };

    const handleRemoveHardware = (uid: string) => {
        setPlacedItemsByView((prev) => ({
            ...prev,
            [modelView]: prev[modelView].filter((item) => item.uid !== uid),
        }));
        if (selectedItemUid === uid) setSelectedItemUid(null);
    };

    const handleUploadDecoration = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(event.target.files || []);
        if (files.length === 0) return;

        const freeSlots = Math.max(0, 5 - customDecorations.filter((decoration) => !decoration.text).length);
        if (freeSlots === 0) {
            event.target.value = "";
            return;
        }

        if (!canUploadCustomDecoration) {
            event.target.value = "";
            return;
        }

        const uploadedImages = await Promise.all(files.slice(0, freeSlots).map(readUploadedImage));
        const nextDecorations = uploadedImages.map(({ src, width, height }, index): HardwareVariant => {
            const longSide = Math.max(width, height) || 1;
            const previewLongSide = 72;
            const defaultWidth = Math.max(24, Math.round((width / longSide) * previewLongSide));
            const defaultHeight = Math.max(24, Math.round((height / longSide) * previewLongSide));
            nextCustomDecorationIdRef.current += 1;

            return {
                id: `custom_${nextCustomDecorationIdRef.current}`,
                categoryId: selectedCategory,
                name: String(customDecorations.length + index + 1).padStart(3, "0"),
                src,
                price: CUSTOM_BASE_PRICE,
                basePrice: CUSTOM_BASE_PRICE,
                defaultWidth,
                defaultHeight,
                minSizeMm: 10,
                maxSizeMm: 300,
                isCustom: true,
            };
        });

        setCustomDecorations((prev) => [...prev, ...nextDecorations]);
        setAreDecorationCaptionsVisible(true);
        event.target.value = "";
    };

    const handleMainPointerDownCapture = (event: React.PointerEvent<HTMLElement>) => {
        if (!isPanelExpanded) return;
        const target = event.target as Element;
        if (panelRef.current?.contains(target)) return;

        setIsPanelExpanded(false);
        setIsCustomizationDetailsOpen(false);

        // The first touch outside the expanded panel dismisses it. Do not let
        // that same pointer gesture reach the canvas and drag the currently
        // selected decoration while the panel is sliding down.
        if (target.closest('[data-constructor-canvas="true"]')) {
            event.preventDefault();
            event.stopPropagation();
        }
    };

    const handlePanelHandlePointerDown = (event: React.PointerEvent<HTMLButtonElement>) => {
        panelDragStartYRef.current = event.clientY;

        const handleMove = (moveEvent: PointerEvent) => {
            if (panelDragStartYRef.current === null) return;
            const deltaY = moveEvent.clientY - panelDragStartYRef.current;

            if (deltaY < -22) {
                setIsPanelExpanded(true);
                setAreDecorationCaptionsVisible(true);
                panelDragStartYRef.current = null;
            }

            if (deltaY > 22) {
                setIsPanelExpanded(false);
                setIsCustomizationDetailsOpen(false);
                panelDragStartYRef.current = null;
            }
        };

        const handleUp = () => {
            panelDragStartYRef.current = null;
            window.removeEventListener("pointermove", handleMove);
            window.removeEventListener("pointerup", handleUp);
        };

        window.addEventListener("pointermove", handleMove);
        window.addEventListener("pointerup", handleUp);
    };

    // Handle vertical panel swipes anywhere on the panel while preserving
    // horizontal decoration scrolling.
    const handlePanelSwipePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
        if ((event.target as HTMLElement).closest("input, textarea, select, a, [data-panel-handle], [data-decoration-scroller]")) return;

        const startX = event.clientX;
        const startY = event.clientY;
        let resolved = false;

        const cleanup = () => {
            window.removeEventListener("pointermove", handleMove);
            window.removeEventListener("pointerup", cleanup);
            window.removeEventListener("pointercancel", cleanup);
        };

        const handleMove = (moveEvent: PointerEvent) => {
            if (resolved) return;
            const deltaX = moveEvent.clientX - startX;
            const deltaY = moveEvent.clientY - startY;
            const action = getPanelSwipeAction({
                isExpanded: isPanelExpanded,
                deltaX,
                deltaY,
                threshold: 28,
            });

            if (action === "expand") {
                resolved = true;
                setIsPanelExpanded(true);
                setAreDecorationCaptionsVisible(true);
                cleanup();
            } else if (action === "collapse") {
                resolved = true;
                setIsPanelExpanded(false);
                setIsCustomizationDetailsOpen(false);
                cleanup();
            } else if (Math.abs(deltaX) > 24 && Math.abs(deltaX) > Math.abs(deltaY) * 1.35) {
                // Horizontal intent (scrolling the decorations) — bail out.
                resolved = true;
                cleanup();
            }
        };

        window.addEventListener("pointermove", handleMove);
        window.addEventListener("pointerup", cleanup);
        window.addEventListener("pointercancel", cleanup);
    };

    const getConstructorCustomization = () => buildConstructorCustomization({
        selectedModel,
        selectedSize,
        selectedFit,
        garmentDimensions,
        placedItemsByView,
        hardwareMap,
        frontImage,
        backImage,
        totalPrice,
        comment,
    });

    const handleBuy = () => {
        if (!selectedModel) return;
        const customization = getConstructorCustomization();
        if (!customization) return;

        const cartPayload: Omit<CartItem, "id"> = {
            product_id: product?.id || 0,
            title: selectedModel.name,
            price: totalPrice,
            image: customization.modelImages[modelView] || selectedModel.src,
            size: selectedSize || "",
            color: editingCartItem?.color || `custom-${Date.now()}`,
            quantity: 1,
            customization,
        };

        if (editingCartItem) {
            updateItem(editingCartItem.id, cartPayload);
            setIsCartOpen(true);
            return;
        }

        addItem(cartPayload);
        setIsCartOpen(true);
    };

    const handleConstructorCartEdit = () => {
        if (!constructorCartItem) return;

        router.push(`/constructor?productId=${constructorCartItem.product_id}&editCartItemId=${encodeURIComponent(constructorCartItem.id)}`);
    };

    const handleSaveDraft = () => {
        if (selectedModel) {
            const customization = getConstructorCustomization();
            if (customization) {
                saveConstructorDraft({
                    draftId: constructorDraftId,
                    productId: product?.id || 0,
                    title: selectedModel.name,
                    imageSrc: customization.modelImages[modelView] || selectedModel.src,
                    draftState: {
                        activeView: modelView,
                        canvasPixelSize: {
                            width: CANVAS_SIZE,
                            height: CANVAS_SIZE,
                        },
                        modelBounds,
                        customization,
                    },
                });
            }
        }

        setIsInstructionMounted(false);
        setIsExitPopupOpen(false);
        router.push("/unfinished");
    };

    const handlePanelPrimaryAction = () => {
        if (!isPanelExpanded) {
            setIsPanelExpanded(true);
            setAreDecorationCaptionsVisible(true);
            return;
        }

        handleBuy();
    };

    const handlePanelSecondaryAction = () => {
        handleSaveDraft();
    };

    const rotateBottom = `calc(var(--constructor-panel-bottom, 5px) + ${panelHeight + ROTATE_PANEL_GAP}px)`;
    const canvasBottomInset = COLLAPSED_PANEL_BASE_HEIGHT + ROTATE_PANEL_GAP + ROTATE_CONTROLS_HEIGHT;
    const decorationViewportHeight = isPanelExpanded ? 205 : areDecorationCaptionsVisible ? 84 : 66;
    const rotateButtonGlassStyle: React.CSSProperties = {
        backdropFilter: "blur(12px) saturate(160%)",
        WebkitBackdropFilter: "blur(12px) saturate(160%)",
        background: "rgba(255, 255, 255, 0.18)",
        border: "1px solid rgba(255, 255, 255, 0.3)",
        boxShadow: "rgba(0, 0, 0, 0.1) 0px 8px 32px, rgba(255, 255, 255, 0.5) 0px 1px 2px inset, rgba(255, 255, 255, 0.05) 0px -1px 2px inset",
        overflow: "hidden",
    };

    const resetConstructorViewportAfterKeyboard = () => {
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;
        window.scrollTo(0, 0);
    };

    return {
        isTextEditorOpen,
        setIsTextEditorOpen,
        openTextEditor,
        saveTextDecoration,
        selectedTextItem,
        editingText: editingTextItem ? hardwareMap[editingTextItem.variantId]?.text : undefined,
        router,
        selectedSize,
        setIsSizeModalOpen,
        selectedFit,
        isSizeModalOpen,
        handleSaveFit,
        isInstructionMounted,
        setIsInstructionMounted,
        isExitPopupOpen,
        setIsExitPopupOpen,
        instructionPortalTarget,
        handleMainPointerDownCapture,
        selectedModel,
        displayActiveImageSrc,
        modelBounds,
        canvasBottomInset,
        placedItems,
        hardwareMap,
        selectedItemUid,
        setSelectedItemUid,
        handleUpdateItem,
        handleRemoveHardware,
        handleCanvasInteraction,
        canvasViewportRef,
        getHardwareScaleLimits,
        rotateButtonGlassStyle,
        isPanelExpanded,
        setIsPanelExpanded,
        modelView,
        glassRefreshId,
        rotateBottom,
        toggleModelView,
        panelBottom,
        panelRef,
        handlePanelSwipePointerDown,
        panelHeight,
        handlePanelHandlePointerDown,
        setAreDecorationCaptionsVisible,
        setIsCustomizationDetailsOpen,
        selectedCategory,
        setSelectedCategory,
        uploadInputRef,
        handleUploadDecoration,
        decorationViewportHeight,
        decorationsScrollerRef,
        revealDecorationCaptionsFromScroll,
        canUploadCustomDecoration,
        areDecorationCaptionsVisible,
        currentVariants,
        getDecorationPanelPrice,
        handleAddHardware,
        decorationPages,
        isCustomizationDetailsOpen,
        customizationPrice,
        placedItemDetails,
        commentInputRef,
        comment,
        setComment,
        resetConstructorViewportAfterKeyboard,
        totalPrice,
        handlePanelSecondaryAction,
        handlePanelPrimaryAction,
        constructorCartItem,
        editingCartItem,
        activeImageSrc,
        handleBuy,
        handleConstructorCartEdit,
        product,
        handleSaveDraft,
    };
};

export type ConstructorPageController = ReturnType<typeof useConstructorPageController>;
