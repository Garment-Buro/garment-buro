"use client";

import { createPortal } from "react-dom";
import { ConstructorExitPopup } from "@/components/shared/ConstructorFlowPopup";
import { CartActionBar } from "@/components/cart/CartActionBar";
import { AdaptiveHeader } from "@/components/layout/AdaptiveHeader";
import { KonvaCanvas } from "@/components/constructor/KonvaCanvas";
import { ConstructorInstructionOverlay } from "@/components/constructor/ConstructorInstructionOverlay";
import { DecorationOptionCard, UploadDecorationCard } from "@/components/constructor/DecorationOptionCard";
import { RotateModelIcon } from "@/components/constructor/RotateModelIcon";
import { SizeFitModal } from "@/components/constructor/SizeFitModal";
import { TextDecorationEditor } from "@/components/constructor/TextDecorationEditor";
import { CONSTRUCTOR_CATEGORIES } from "@/lib/constructor/config/categories";
import { IMAGE_FILE_ACCEPT } from "@/lib/media/utils/upload";
import { formatCm } from "@/lib/constructor/utils/constructor";
import type { ConstructorPageController } from "@/hooks/constructor/useConstructorPageController";

export const ConstructorWorkspace = ({ controller }: { controller: ConstructorPageController }) => {
    const {
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
    } = controller;

    return (
        <div
            className="constructorViewport relative w-full touch-none overflow-hidden bg-white"
            style={{
                backgroundImage: "url('/constructor_bg.webp')",
                backgroundSize: "cover",
                backgroundPosition: "center",
                backgroundRepeat: "no-repeat",
            }}
        >
            <div className="constructorVisibleViewport relative flex w-full flex-col overflow-hidden">
                <div className="constructorSafariTop" aria-hidden="true" />

                <AdaptiveHeader
                    variant="constructor"
                    fixed={false}
                    topOffset={0}
                    className="constructorHeaderFlush"
                    sizeLabel={selectedSize ? `Размер: ${selectedSize}` : "Цвет/Размер"}
                    onSizeClick={() => {
                        setIsInstructionMounted(false);
                        setIsSizeModalOpen(true);
                    }}
                    elevateSizeButton={isInstructionMounted && !isSizeModalOpen && !isExitPopupOpen}
                    onLogoClick={() => {
                        setIsInstructionMounted(false);
                        setIsExitPopupOpen(true);
                    }}
                />

                <main
                    className="relative flex w-full flex-1 flex-col overflow-hidden"
                    onPointerDownCapture={handleMainPointerDownCapture}
                >
                <div className="absolute inset-0 z-0">
                    <KonvaCanvas
                        selectedModel={selectedModel}
                        activeImageSrc={displayActiveImageSrc || undefined}
                        modelBounds={modelBounds}
                        bottomInset={canvasBottomInset}
                        placedItems={placedItems}
                        hardwareMap={hardwareMap}
                        selectedHardwareUid={selectedItemUid}
                        onSelectHardware={setSelectedItemUid}
                        onUpdateItem={handleUpdateItem}
                        onRemoveHardware={handleRemoveHardware}
                        onCanvasInteraction={handleCanvasInteraction}
                        onViewportChange={(viewport) => {
                            canvasViewportRef.current = viewport;
                        }}
                        getHardwareScaleLimits={getHardwareScaleLimits}
                    />
                </div>

                <button
                    type="button"
                    aria-label="Назад"
                    onClick={() => setIsExitPopupOpen(true)}
                    className="absolute left-[10px] top-[10px] z-30 flex h-[30px] w-[30px] items-center justify-center rounded-[10px] p-0 transition active:scale-[0.98]"
                    style={rotateButtonGlassStyle}
                >
                    <svg xmlns="http://www.w3.org/2000/svg" width="21" height="24" viewBox="0 0 30 30" fill="none" aria-hidden="true">
                        <path d="M15 9L8 15L15 21" stroke="#A2A2A2" strokeLinecap="round" strokeLinejoin="round" />
                        <path d="M8 15L22 15" stroke="#A2A2A2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                </button>

                {controller.selectedTextItem && (
                    <button type="button" onClick={() => controller.openTextEditor(controller.selectedTextItem!.uid)}
                        className="absolute right-[10px] top-[10px] z-30 rounded-[10px] bg-white px-4 py-2 text-[13px] shadow-sm">
                        Изменить текст
                    </button>
                )}

                {!isPanelExpanded && (
                    <div
                        key={`rotate-controls-${modelView}-${selectedItemUid || "empty"}-${glassRefreshId}`}
                        className="absolute left-[5px] right-[5px] z-20 flex items-center justify-between transition-opacity duration-200 md:left-1/2 md:right-auto md:w-[min(600px,calc(100%-10px))] md:-translate-x-1/2"
                        style={{ bottom: rotateBottom }}
                    >
                        <button
                            type="button"
                            onClick={toggleModelView}
                            className="flex h-[45px] w-[90px] items-center justify-center rounded-[14px] p-0 transition active:scale-95"
                            style={rotateButtonGlassStyle}
                            aria-label="Повернуть изделие влево"
                        >
                            <RotateModelIcon direction="left" />
                        </button>

                        <div className="flex flex-col items-center gap-[7px] text-center font-manrope text-[10px] font-semibold uppercase leading-none text-[#A0A0A0]">
                            <span>{modelView === "front" ? "вид спереди" : "вид сзади"}</span>
                            <span>повернуть</span>
                        </div>

                        <button
                            type="button"
                            onClick={toggleModelView}
                            className="flex h-[45px] w-[90px] items-center justify-center rounded-[14px] p-0 transition active:scale-95"
                            style={rotateButtonGlassStyle}
                            aria-label="Повернуть изделие вправо"
                        >
                            <RotateModelIcon direction="right" />
                        </button>
                    </div>
                )}

                <section
                    className="absolute left-[5px] right-[5px] z-20 md:left-1/2 md:right-auto md:w-[min(600px,calc(100%-10px))] md:-translate-x-1/2"
                    style={{ bottom: panelBottom }}
                >
                    <div
                        ref={panelRef}
                        onPointerDownCapture={handlePanelSwipePointerDown}
                        className="relative overflow-hidden rounded-[15px] bg-white transition-[height] duration-500 ease-out"
                        style={{ height: panelHeight }}
                    >
                        <button
                            type="button"
                            data-panel-handle
                            aria-label={isPanelExpanded ? "Свернуть панель украшений" : "Развернуть панель украшений"}
                            onPointerDown={handlePanelHandlePointerDown}
                            onClick={() => {
                                setIsPanelExpanded((value) => !value);
                                setAreDecorationCaptionsVisible(true);
                                if (isPanelExpanded) setIsCustomizationDetailsOpen(false);
                            }}
                            className="mx-auto mt-[5px] flex h-[14px] w-[54px] cursor-row-resize items-center justify-center touch-none"
                        >
                            <span className="h-[1.5px] w-[48px] rounded-[15px] bg-[#D5D5D5] shadow-[0_0.5px_0.5px_0_rgba(0,0,0,0.25)_inset]" />
                        </button>

                        <div className="mt-[5px] overflow-x-auto px-[25px] scrollbar-hide">
                            <div className="flex w-max items-center gap-[30px] after:block after:w-[25px] after:shrink-0 after:content-['']">
                                <button type="button" onClick={() => controller.openTextEditor()} className="whitespace-nowrap font-manrope text-[12px] font-semibold text-black">Текст +</button>
                        {CONSTRUCTOR_CATEGORIES.map((cat) => (
                                    <button
                                        key={cat.id}
                                        type="button"
                                        onClick={() => setSelectedCategory(cat.id)}
                                        className={`whitespace-nowrap text-center font-manrope text-[12px] font-semibold leading-[150%] tracking-[0.6px] transition ${
                                            cat.id === "embroidery" ? "text-[#A0A0A0]" : selectedCategory === cat.id ? "text-black" : "text-[#A0A0A0]"
                                        }`}
                                    >
                                        {cat.name}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="mt-[3px] h-[0.7px] bg-[#EEE]" />

                        <input
                            ref={uploadInputRef}
                            type="file"
                            accept={IMAGE_FILE_ACCEPT}
                            multiple
                            onChange={handleUploadDecoration}
                            className="hidden"
                        />

                        {!isPanelExpanded ? (
                            <div
                                className="overflow-hidden transition-[max-height] duration-500 ease-out"
                                style={{ maxHeight: decorationViewportHeight }}
                            >
                                <div
                                    ref={decorationsScrollerRef}
                                    data-decoration-scroller
                                    className="mt-[10px] flex gap-[15px] overflow-x-auto px-[25px] scrollbar-hide"
                                    onScroll={revealDecorationCaptionsFromScroll}
                                >
                                    {canUploadCustomDecoration && (
                                        <UploadDecorationCard
                                            variant="rail"
                                            captionsVisible={areDecorationCaptionsVisible}
                                            onUpload={() => uploadInputRef.current?.click()}
                                        />
                                    )}

                                    {currentVariants.map((variant) => (
                                        <DecorationOptionCard
                                            key={variant.id}
                                            decoration={variant}
                                            priceLabel={variant.price > 0 ? getDecorationPanelPrice(variant) : ""}
                                            variant="rail"
                                            captionsVisible={areDecorationCaptionsVisible}
                                            onSelect={handleAddHardware}
                                        />
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div ref={decorationsScrollerRef} data-decoration-scroller className="mt-[10px] overflow-x-auto scrollbar-hide [scroll-snap-type:x_mandatory]">
                                <div className="flex">
                                    {decorationPages.map((page, pageIndex) => (
                                        <div
                                            key={pageIndex}
                                            className="min-w-full shrink-0 px-[20px] [scroll-snap-align:start]"
                                        >
                                            <div className="grid grid-cols-5 justify-items-center gap-y-[10px]">
                                                {pageIndex === 0 && canUploadCustomDecoration && (
                                                    <UploadDecorationCard
                                                        variant="grid"
                                                        onUpload={() => uploadInputRef.current?.click()}
                                                    />
                                                )}

                                                {page.map((variant) => (
                                                    <DecorationOptionCard
                                                        key={variant.id}
                                                        decoration={variant}
                                                        priceLabel={variant.price > 0 ? getDecorationPanelPrice(variant) : ""}
                                                        variant="grid"
                                                        onSelect={handleAddHardware}
                                                    />
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div
                            aria-hidden={!isPanelExpanded}
                            className={`absolute bottom-[75px] left-[40px] right-[40px] h-[190px] overflow-hidden ${
                                isPanelExpanded ? "pointer-events-auto" : "pointer-events-none"
                            }`}
                        >
                            <div className={`flex h-full flex-col overflow-hidden font-manrope text-[10px] font-medium text-[#2D2D2D] transition-transform duration-500 ease-out ${
                                isPanelExpanded ? "translate-y-0" : "translate-y-full"
                            }`}>
                                <div className={`min-h-0 flex-1 overflow-y-auto scrollbar-hide ${isCustomizationDetailsOpen ? "pt-0" : "pt-[36px]"}`}>
                                    <div className="flex items-center justify-between">
                                        <span className="max-w-[60%] truncate" title={selectedModel?.name || "Товар"}>{selectedModel?.name || "Товар"}</span>
                                        <span className="text-right">{(selectedModel?.price || 0).toLocaleString("ru-RU")} ₽</span>
                                    </div>

                                    <button
                                        type="button"
                                        onClick={() => setIsCustomizationDetailsOpen((value) => !value)}
                                        className="mt-[8px] flex w-full items-center justify-between text-left transition active:scale-[0.99]"
                                    >
                                        <span className="flex items-center">
                                            <span>Кастомизация</span>
                                            <svg
                                                className={`ml-[10px] h-[8px] w-[8px] transition-transform ${isCustomizationDetailsOpen ? "rotate-180" : ""}`}
                                                viewBox="0 0 8 8"
                                                aria-hidden="true"
                                            >
                                                <path d="M1 3L4 6L7 3" fill="none" stroke="#454545" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" />
                                            </svg>
                                        </span>
                                        <span>{customizationPrice.toLocaleString("ru-RU")} ₽</span>
                                    </button>

                                    {isCustomizationDetailsOpen && (
                                        <div className="mt-[9px] flex max-h-[120px] flex-col gap-[6px] overflow-y-auto pr-1 text-[#A0A0A0] scrollbar-hide">
                                            {placedItemDetails.length > 0 ? placedItemDetails.map((detail) => (
                                                <div key={detail.item.uid} className="flex items-center justify-between">
                                                    <span className="max-w-[68%] truncate" title={`${detail.hardware?.name || "Украшение"} · ${formatCm(detail.widthCm)} × ${formatCm(detail.heightCm)}`}>
                                                        {detail.hardware?.name || "Украшение"} · {formatCm(detail.widthCm)} × {formatCm(detail.heightCm)}
                                                    </span>
                                                    <span>{detail.price.toLocaleString("ru-RU")} ₽</span>
                                                </div>
                                            )) : (
                                                <div className="flex items-center justify-between">
                                                    <span>украшения не добавлены</span>
                                                    <span>0 ₽</span>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    <label className="mt-[18px] flex items-center gap-[12px] text-[#9B9B9B]">
                                        <svg width="19" height="19" viewBox="0 0 19 19" fill="none" aria-hidden="true" className="shrink-0">
                                            <path d="M4.1 3.5H14.9C16 3.5 16.9 4.4 16.9 5.5V11.8C16.9 12.9 16 13.8 14.9 13.8H8.2L4.4 16.2V13.8H4.1C3 13.8 2.1 12.9 2.1 11.8V5.5C2.1 4.4 3 3.5 4.1 3.5Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
                                        </svg>
                                        <input
                                            ref={commentInputRef}
                                            value={comment}
                                            onChange={(event) => setComment(event.target.value)}
                                            onFocus={() => {
                                                setIsPanelExpanded(true);
                                            }}
                                            onBlur={() => {
                                                resetConstructorViewportAfterKeyboard();
                                                window.setTimeout(resetConstructorViewportAfterKeyboard, 120);
                                                window.setTimeout(resetConstructorViewportAfterKeyboard, 320);
                                            }}
                                            className="min-w-0 flex-1 border-0 border-b border-[#D5D5D5] bg-transparent pb-[6px] font-manrope text-[16px] font-medium leading-none text-[#2D2D2D] outline-none placeholder:text-[12px] placeholder:text-[#9B9B9B]"
                                            placeholder="Комментарий"
                                        />
                                    </label>
                                </div>

                                <div className="mt-[20px] h-px shrink-0 bg-[#EEEEEE]" />
                                <div className="mt-[18px] flex shrink-0 items-center justify-between text-[14px] font-semibold text-[#2D2D2D]">
                                    <span>Итого</span>
                                    <span>{totalPrice.toLocaleString("ru-RU")} ₽</span>
                                </div>
                            </div>
                        </div>

                        <div className="absolute bottom-0 left-0 right-0 z-10 flex h-[35px] items-center justify-between bg-white px-[40px] font-manrope text-[14px] font-semibold leading-none text-[#676767]">
                            <button type="button" onClick={handlePanelSecondaryAction} className="flex h-full w-[100px] items-center justify-center appearance-none bg-transparent text-center transition active:scale-95">
                                СОХРАНИТЬ
                            </button>
                            <span className="h-[15px] w-[2px] shrink-0 rounded-[15px] bg-[#9D9D9D] shadow-[0_0.5px_0.5px_0_rgba(0,0,0,0.25)_inset]" />
                            <button type="button" onClick={handlePanelPrimaryAction} className="flex h-full w-[100px] items-center justify-center appearance-none border-0 bg-transparent p-0 text-center transition active:scale-95">
                                {isPanelExpanded ? "КУПИТЬ" : "ДАЛЕЕ"}
                            </button>
                        </div>
                    </div>
                </section>

                </main>

                <CartActionBar
                    visible={false}
                    title={constructorCartItem?.title || selectedModel?.name || "Товар"}
                    color={constructorCartItem?.color || editingCartItem?.color || ""}
                    price={constructorCartItem?.price || totalPrice}
                    image={constructorCartItem?.image || activeImageSrc || selectedModel?.src || "/landing-bg.webp"}
                    cartItemId={constructorCartItem?.id}
                    usePreferredCartItemOnly
                    showAddProductCard={false}
                    disabled={false}
                    onAdd={handleBuy}
                    onEdit={handleConstructorCartEdit}
                    onBuy={() => router.push("/checkout")}
                />

                <ConstructorInstructionOverlay
                    isOpen={isInstructionMounted}
                    portalTarget={instructionPortalTarget}
                    onDismiss={() => setIsInstructionMounted(false)}
                />

                {isSizeModalOpen && instructionPortalTarget
                    ? createPortal(
                        <SizeFitModal
                            product={product}
                            selectedSize={selectedSize}
                            selectedFit={selectedFit}
                            productImageSrc={displayActiveImageSrc}
                            onSave={handleSaveFit}
                            onClose={() => setIsSizeModalOpen(false)}
                        />,
                        instructionPortalTarget,
                    )
                    : null}

                <ConstructorExitPopup
                    isOpen={isExitPopupOpen}
                    onClose={() => setIsExitPopupOpen(false)}
                    onLeave={() => {
                        setIsExitPopupOpen(false);
                        router.push("/");
                    }}
                    onSave={handleSaveDraft}
                />
                {controller.isTextEditorOpen && createPortal(
                    <TextDecorationEditor
                        initialValue={controller.editingText}
                        onClose={() => { controller.setIsTextEditorOpen(false); resetConstructorViewportAfterKeyboard(); }}
                        onSave={controller.saveTextDecoration}
                    />,
                    document.body,
                )}
            </div>
        </div>
    );
};
