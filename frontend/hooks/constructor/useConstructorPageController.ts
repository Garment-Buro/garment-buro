"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { readLegacyConstructorDraft } from "@/lib/projects/legacyRecords";
import { useCustomerProject } from "@/hooks/projects/useCustomerProject";
import { isCustomerSessionCurrent } from "@/hooks/catalog/customerSession";
import { useConstructorPageEnvironment } from "@/hooks/constructor/useConstructorPageEnvironment";
import { useConstructorProduct } from "@/hooks/constructor/useConstructorProduct";
import { useConstructorDerivedState } from "@/hooks/constructor/useConstructorDerivedState";
import { useConstructorPointerSession } from "@/hooks/constructor/useConstructorPointerSession";
import { useConstructorCartPreparation } from "@/hooks/constructor/useConstructorCartPreparation";
import { constructorPublicImages } from "@/lib/constructor/cartPreparation";
import { ApiError } from "@/lib/api/http";
import { getNextDecorationDropPosition, getPanelSwipeAction } from "@/lib/constructor/utils/interaction";
import { COLLAPSED_PANEL_BASE_HEIGHT, ROTATE_CONTROLS_HEIGHT, ROTATE_PANEL_GAP } from "@/lib/constructor/constants";
import type {
    CanvasViewport,
    ConstructorDraftState,
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
    getCustomDecorationsFromCustomization,
    getConstructorDraftFromCartItem,
    getFirstAvailableSize,
    getHardwareScaleLimits,
    getPlacedItemsFromCartItem,
    getPlacedItemsFromCustomization,
    getProductDimensions,
    readUploadedImage,
    resolveConstructorGeometry,
} from "@/lib/constructor/utils/constructor";
import { useCartStore } from "@/store/cartStore";
import { constructorCartPayload, constructorSelectionStock, restoreConstructorSelection } from '@/lib/constructor/selection';

export const useConstructorPageController = ({
    productId: initialProductId = null,
    editCartItemId: initialEditCartItemId = null,
    draftId: initialDraftId = null,
    projectId: initialProjectId = null,
}: ConstructorPageProps = {}) => {
    const router = useRouter();
    const panelGesture = useConstructorPointerSession();
    const projectSession = useCustomerProject(initialProjectId);
    const cartPreparation = useConstructorCartPreparation();
    const [isSignInOpen, setIsSignInOpen] = useState(false);
    const [saveNotice, setSaveNotice] = useState<string | null>(null);
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
    const [isInstructionMounted, setIsInstructionMounted] = useState(!initialDraftId && !initialProjectId);
    const [restoredDraftModelImages, setRestoredDraftModelImages] = useState<Record<ModelView, string> | null>(null);
    const [restoredDraftGeometry, setRestoredDraftGeometry] = useState<ConstructorDraftState | null>(null);
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
    const loadedServerDraftRef = useRef<ConstructorDraftState | null>(null);
    const imageInputLifetime = useRef<AbortController | null>(null);
    const readingImages = useRef(false);
    const [glassRefreshId, setGlassRefreshId] = useState(0);
    const { items, activeItemId, addItem, updateItem, setIsCartOpen } = useCartStore();
    const editingCartItem = useMemo(
        () => (editCartItemId ? items.find((item) => item.id === editCartItemId) : undefined),
        [editCartItemId, items],
    );
    const constructorCartItem = useMemo(() => {
        if (editCartItemId) return editingCartItem;

        const activeItem = activeItemId ? items.find((item) => item.id === activeItemId) : undefined;
        return editingCartItem || activeItem || items[items.length - 1];
    }, [activeItemId, editCartItemId, editingCartItem, items]);
    const productIdToLoad = initialProjectId
        ? projectSession.document?.product_id
            ? String(projectSession.document.product_id)
            : null
        : constructorProductId || (editingCartItem?.product_id ? String(editingCartItem.product_id) : null);
    const {
        product,
        selectedSize,
        selectedColor,
        selectionAvailable,
        restoreSelection,
        selectedFit,
        isSizeModalOpen,
        setIsSizeModalOpen,
        handleSaveFit: saveProductFit,
        error: productError,
        retry: retryProduct,
    } = useConstructorProduct(productIdToLoad);
    const isConstructorOverlayActive = isInstructionMounted || isSizeModalOpen || isExitPopupOpen;
    const instructionPortalTarget = useConstructorPageEnvironment(isConstructorOverlayActive);

    useEffect(() => {
        setIsCartOpen(false);
    }, [editCartItemId, setIsCartOpen]);

    useEffect(() => {
        if (!editingCartItem || !product) return;
        if (loadedEditCartItemIdRef.current === editingCartItem.id) return;

        const editSize = editingCartItem.customization?.selectedSize ?? editingCartItem.size ?? getFirstAvailableSize(product);
        const restored = getConstructorDraftFromCartItem(editingCartItem);
        const editFit = editingCartItem.customization?.fit || createDefaultFit(editSize, restored?.customization.garment || getProductDimensions(product, editSize, editingCartItem.color));
        const restoredPlacedItems = getPlacedItemsFromCartItem(editingCartItem);
        const restoredCustomDecorations = getCustomDecorationsFromCustomization(editingCartItem.customization,
            resolveConstructorGeometry(product, editSize, restored).pixelsPerCm);
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
            restoreSelection(editSize, editFit, editingCartItem.color);
            setComment(editingCartItem.customization?.comment || "");
            setPlacedItemsByView({
                front: restoredPlacedItems.front,
                back: restoredPlacedItems.back,
            });
            setCustomDecorations(restoredCustomDecorations);
            setRestoredDraftModelImages(restored?.customization.modelImages || null);
            setRestoredDraftGeometry(restored ? { ...restored, customization: { ...restored.customization, selectedColor: editingCartItem.color } } : null);
            setModelView(restored?.activeView || 'front');
            setSelectedItemUid(null);
            setAreDecorationCaptionsVisible(restoredDecorations.length > 0);
            nextItemIdRef.current = maxItemIndex;
            nextCustomDecorationIdRef.current = maxCustomDecorationIndex;
            loadedEditCartItemIdRef.current = editingCartItem.id;
        });

        return () => {
            window.cancelAnimationFrame(frameId);
        };
    }, [editingCartItem, product, restoreSelection]);

    useEffect(() => {
        if (!product || editCartItemId) return;
        const serverDraft = projectSession.restored;
        if (serverDraft && loadedServerDraftRef.current === serverDraft) return;
        if (!serverDraft && (initialProjectId || !constructorDraftId || loadedDraftIdRef.current === constructorDraftId)) return;
        const draftState = serverDraft || readLegacyConstructorDraft(constructorDraftId!)?.draftState;
        if (!draftState) return;

        const { customization } = draftState;
        const restoredPlacedItems = getPlacedItemsFromCustomization(customization);
        const restoredCustomDecorations = getCustomDecorationsFromCustomization(
            customization,
            resolveConstructorGeometry(product, customization.selectedSize, draftState).pixelsPerCm,
        );
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
            restoreSelection(customization.selectedSize,
                customization.fit || createDefaultFit(customization.selectedSize, customization.garment), customization.selectedColor);
            setComment(customization.comment || "");
            setPlacedItemsByView(restoredPlacedItems);
            setCustomDecorations(restoredCustomDecorations);
            setRestoredDraftModelImages(customization.modelImages);
            setRestoredDraftGeometry({ ...draftState, customization: { ...customization,
                selectedColor: restoreConstructorSelection(product, customization.selectedSize, customization.selectedColor).color } });
            setModelView(draftState.activeView);
            setSelectedItemUid(null);
            setAreDecorationCaptionsVisible(customization.decorations.length > 0);
            setIsInstructionMounted(false);
            nextItemIdRef.current = maxItemIndex;
            nextCustomDecorationIdRef.current = maxCustomDecorationIndex;
            loadedDraftIdRef.current = constructorDraftId;
            loadedServerDraftRef.current = serverDraft ? draftState : null;
        });

        return () => window.cancelAnimationFrame(frameId);
    }, [constructorDraftId, initialProjectId, projectSession.restored, editCartItemId, product, restoreSelection]);

    const handleSaveFit = (fit: NonNullable<typeof selectedFit>, color: string | null) => {
        if (constructorSelectionStock(product, { size: fit.selectedSize, color }) <= 0) return;
        if (fit.selectedSize !== selectedSize || color !== selectedColor) {
            setRestoredDraftModelImages(null);
        }
        saveProductFit(fit, color);
    };

    useEffect(() => {
        decorationsScrollerRef.current?.scrollTo({ left: 0 });
    }, [isPanelExpanded, selectedCategory]);

    useEffect(
        () => () => {
            if (captionsRevealTimerRef.current) {
                window.clearTimeout(captionsRevealTimerRef.current);
            }
        },
        [],
    );

    useEffect(() => {
        const lifetime = new AbortController();
        imageInputLifetime.current = lifetime;
        return () => lifetime.abort();
    }, []);

    const {
        frontImage,
        backImage,
        activeImageSrc,
        displayActiveImageSrc,
        placedItems,
        garmentDimensions,
        modelBounds,
        geometry,
        canUploadCustomDecoration,
        selectedModel,
        currentVariants,
        hardwareMap,
        customizationPrice,
        totalPrice,
        pricing,
        decorationPrices,
        placedItemDetails,
        decorationPages,
        getDecorationPanelPrice,
    } = useConstructorDerivedState({
        product,
        selectedSize,
        selectedColor,
        modelView,
        selectedCategory,
        customDecorations,
        placedItemsByView,
        selectedItemUid,
        restoredModelImages: restoredDraftModelImages,
        restoredDraft: restoredDraftGeometry,
        selectedFit,
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
        const viewport = canvasViewportRef.current;
        // Drop the new decoration slightly above the centre of the area that
        // remains visible above the decorations panel (even when it is fully
        // expanded), so it is always on screen right after being added.
        const visibleAreaHeight = viewport
            ? Math.max(120, viewport.height - (panelHeight + panelBottomForCanvas))
            : geometry.canvasPixelSize.height;
        const targetScreenY = viewport ? visibleAreaHeight / 2 : geometry.canvasPixelSize.height * 0.42;
        const centerPoint = viewport
            ? {
                  x: clampCanvasPoint((viewport.width / 2 - viewport.stagePos.x) / viewport.stageScale, geometry.canvasPixelSize.width),
                  y: clampCanvasPoint((targetScreenY - viewport.stagePos.y) / viewport.stageScale, geometry.canvasPixelSize.height),
              }
            : {
                  x: geometry.canvasPixelSize.width / 2,
                  y: geometry.canvasPixelSize.height * 0.42,
              };
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
                        canvasSize: geometry.canvasPixelSize,
                    }),
                    scale: hardware?.text ? Math.min(1, 300 / Math.max(hardware.defaultWidth, hardware.defaultHeight || 1)) : 1,
                    rotation: 0,
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
            categoryId: "prints",
            name: result.text.content,
            src: result.src,
            text: result.text,
            defaultWidth: result.width,
            defaultHeight: result.height,
            price: 0,
            minSizeMm: 10,
            maxSizeMm: 600,
            isCustom: true,
        };
        const oldVariantStillUsed =
            editingTextItem &&
            Object.values(placedItemsByView)
                .flat()
                .some((item) => item.uid !== editingTextItem.uid && item.variantId === editingTextItem.variantId);
        setCustomDecorations((previous) => [
            ...previous.filter((entry) => !editingTextItem || oldVariantStillUsed || entry.id !== editingTextItem.variantId),
            variant,
        ]);
        if (editingTextItem) {
            setPlacedItemsByView((previous) => ({
                ...previous,
                [modelView]: previous[modelView].map((item) =>
                    item.uid === editingTextItem.uid
                        ? {
                              ...item,
                              variantId: variant.id,
                          }
                        : item,
                ),
            }));
        } else {
            handleAddHardware(variant.id, variant);
        }
        setSelectedCategory("prints");
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
        const signal = imageInputLifetime.current?.signal;
        if (!signal || signal.aborted || readingImages.current) return;
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

        const input = event.target;
        readingImages.current = true;
        try {
            const uploadedImages = await Promise.all(files.slice(0, freeSlots).map((file) => readUploadedImage(file, signal)));
            if (signal.aborted) return;
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
                    price: 0,
                    defaultWidth,
                    defaultHeight,
                    minSizeMm: 10,
                    maxSizeMm: 300,
                    isCustom: true,
                };
            });

            setCustomDecorations((prev) => [...prev, ...nextDecorations]);
            setAreDecorationCaptionsVisible(true);
        } catch (error) {
            if (!signal.aborted) setSaveNotice(error instanceof Error ? error.message : "Не удалось прочитать изображение.");
        } finally {
            readingImages.current = false;
            input.value = "";
        }
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
        panelGesture.cancel();
        panelDragStartYRef.current = event.clientY;

        const handleMove = (moveEvent: PointerEvent) => {
            if (panelDragStartYRef.current === null) return;
            const deltaY = moveEvent.clientY - panelDragStartYRef.current;

            if (deltaY < -22) {
                setIsPanelExpanded(true);
                setAreDecorationCaptionsVisible(true);
                panelGesture.cancel();
            }

            if (deltaY > 22) {
                setIsPanelExpanded(false);
                setIsCustomizationDetailsOpen(false);
                panelGesture.cancel();
            }
        };

        const reset = () => { panelDragStartYRef.current = null; };
        panelGesture.start(event.pointerId, { onMove: handleMove, onEnd: reset, onCancel: reset });
    };

    // Handle vertical panel swipes anywhere on the panel while preserving
    // horizontal decoration scrolling.
    const handlePanelSwipePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
        if ((event.target as HTMLElement).closest("input, textarea, select, a, [data-panel-handle], [data-decoration-scroller]")) return;

        const startX = event.clientX;
        const startY = event.clientY;
        panelGesture.cancel();

        const handleMove = (moveEvent: PointerEvent) => {
            const deltaX = moveEvent.clientX - startX;
            const deltaY = moveEvent.clientY - startY;
            const action = getPanelSwipeAction({
                isExpanded: isPanelExpanded,
                deltaX,
                deltaY,
                threshold: 28,
            });

            if (action === "expand") {
                setIsPanelExpanded(true);
                setAreDecorationCaptionsVisible(true);
                panelGesture.cancel();
            } else if (action === "collapse") {
                setIsPanelExpanded(false);
                setIsCustomizationDetailsOpen(false);
                panelGesture.cancel();
            } else if (Math.abs(deltaX) > 24 && Math.abs(deltaX) > Math.abs(deltaY) * 1.35) {
                // Horizontal intent (scrolling the decorations) — bail out.
                panelGesture.cancel();
            }
        };

        panelGesture.start(event.pointerId, { onMove: handleMove });
    };

    const getConstructorCustomization = () =>
        buildConstructorCustomization({
            selectedModel,
            selectedSize,
            selectedColor: selectedColor ?? undefined,
            selectedFit,
            garmentDimensions,
            placedItemsByView,
            hardwareMap,
            frontImage,
            backImage,
            totalPrice,
            comment,
            geometry,
            decorationPrices,
        });

    const handleBuy = async () => {
        if (
            !selectedModel ||
            !product ||
            !pricing.quote ||
            !selectionAvailable ||
            projectSession.status !== "idle" || cartPreparation.isPreparing ||
            (projectSession.isExisting && (!projectSession.restored || projectSession.error))
        )
            return;
        if (editCartItemId && !editingCartItem) {
            setSaveNotice("Товар удалён из корзины. Откройте корзину заново.");
            return;
        }
        const customization = getConstructorCustomization();
        if (!customization) return;

        const cartPayload = constructorCartPayload(product, { size: selectedSize, color: selectedColor }, customization, modelView);
        if (!cartPayload) return;

        const projectImages = projectSession.editor.getImageSources();
        setSaveNotice(null);
        try {
            await cartPreparation.submit(cartPayload, {
                publicImages: new Set([...constructorPublicImages(product), ...projectImages.publicImages]),
                privateImages: projectImages.privateImages,
            }, durable => {
                if (editingCartItem) {
                    const current = useCartStore.getState().items.find(item => item.id === editingCartItem.id);
                    if (JSON.stringify(current) !== JSON.stringify(editingCartItem)) throw new Error("Товар в корзине изменился. Откройте его заново перед сохранением дизайна.");
                    updateItem(editingCartItem.id, { ...durable, quantity: editingCartItem.quantity });
                } else addItem(durable);
                setIsCartOpen(true);
            });
        } catch (error) {
            if (error instanceof Error && error.name === 'AbortError') return;
            setSaveNotice(error instanceof ApiError
                ? error.status === 404 ? "Изображение проекта недоступно. Откройте проект заново или загрузите файл ещё раз."
                    : "Не удалось сохранить изображения. Изменения остались в редакторе. Нажмите «Купить» ещё раз."
                : error instanceof Error ? error.message : "Не удалось сохранить изображения. Попробуйте ещё раз.");
        }
    };

    const handleConstructorCartEdit = () => {
        if (!constructorCartItem) return;

        router.push(
            `/constructor?productId=${constructorCartItem.product_id}&editCartItemId=${encodeURIComponent(constructorCartItem.id)}`,
        );
    };

    const handleSaveDraft = async () => {
        if (!selectedModel || !product || projectSession.status !== "idle" || cartPreparation.isPreparing) return;
        if (!projectSession.account.sessionReady) {
            setSaveNotice("Восстанавливаем сессию…");
            return;
        }
        if (!projectSession.account.userId) {
            setIsExitPopupOpen(false);
            setIsSignInOpen(true);
            return;
        }
        const customization = getConstructorCustomization();
        if (!customization) return;
        const { userId, key } = projectSession.account;
        setSaveNotice(null);
        setIsExitPopupOpen(false);
        const result = await projectSession.editor.save({
            productId: product.id,
            title: projectSession.document?.title || selectedModel.name,
            kind: projectSession.document?.kind || "draft",
            assets: product.media_assets || [],
            draft: {
                activeView: modelView,
                canvasPixelSize: geometry.canvasPixelSize,
                modelBounds,
                customization,
            },
        });
        if (!result || !isCustomerSessionCurrent(userId, key)) return;
        if (!result.matchesDraft) {
            setSaveNotice("Предыдущая попытка сохранена. Нажмите «Сохранить» ещё раз, чтобы записать текущие изменения.");
            return;
        }
        setSaveNotice("Сохранено в аккаунте.");
        setIsInstructionMounted(false);
        // The durable URL also makes reload and opening on another device real.
        if (!initialProjectId) router.replace(`/constructor?projectId=${result.document.id}`);
    };

    const handlePanelPrimaryAction = () => {
        if (!isPanelExpanded) {
            setIsPanelExpanded(true);
            setAreDecorationCaptionsVisible(true);
            return;
        }

        void handleBuy();
    };

    const handlePanelSecondaryAction = () => {
        void handleSaveDraft();
    };

    const rotateBottom = `calc(var(--constructor-panel-bottom, 5px) + ${panelHeight + ROTATE_PANEL_GAP}px)`;
    const canvasBottomInset = COLLAPSED_PANEL_BASE_HEIGHT + ROTATE_PANEL_GAP + ROTATE_CONTROLS_HEIGHT;
    const decorationViewportHeight = isPanelExpanded ? 205 : areDecorationCaptionsVisible ? 84 : 66;
    const rotateButtonGlassStyle: React.CSSProperties = {
        backdropFilter: "blur(12px) saturate(160%)",
        WebkitBackdropFilter: "blur(12px) saturate(160%)",
        background: "rgba(255, 255, 255, 0.18)",
        border: "1px solid rgba(255, 255, 255, 0.3)",
        boxShadow:
            "rgba(0, 0, 0, 0.1) 0px 8px 32px, rgba(255, 255, 255, 0.5) 0px 1px 2px inset, rgba(255, 255, 255, 0.05) 0px -1px 2px inset",
        overflow: "hidden",
    };

    const resetConstructorViewportAfterKeyboard = () => {
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;
        window.scrollTo(0, 0);
    };

    return {
        projectSession,
        cartPreparation,
        isProductExpected: Boolean(productIdToLoad),
        productError,
        retryProduct,
        isSignInOpen,
        setIsSignInOpen,
        saveNotice,
        isTextEditorOpen,
        setIsTextEditorOpen,
        openTextEditor,
        saveTextDecoration,
        selectedTextItem,
        editingText: editingTextItem ? hardwareMap[editingTextItem.variantId]?.text : undefined,
        router,
        selectedSize,
        selectedColor,
        selectionAvailable,
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
        getHardwareScaleLimits: (item: PlacedHardware, hardware: HardwareVariant) =>
            getHardwareScaleLimits(item, hardware, geometry.pixelsPerCm),
        canvasPixelSize: geometry.canvasPixelSize,
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
        pricing,
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
