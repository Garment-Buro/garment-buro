"use client";

import Image from 'next/image';
import React from 'react';
import type { CartActionBarProps } from '@/lib/cart/actionTypes';
import {
    CART_ACTION_CONTENT_GLOW_COLLAPSED_GRADIENT,
    CART_ACTION_CONTENT_GLOW_COLLAPSED_HEIGHT,
    CART_ACTION_CONTENT_GLOW_EXPANDED_GRADIENT,
    CART_ACTION_CONTENT_GLOW_EXPANDED_HEIGHT,
    CART_ACTION_ENTER_MS,
    CART_ACTION_EXIT_MS,
    CART_ACTION_EXPAND_MS,
    CART_ACTION_EXPANDED_BOTTOM_LIFT,
    CART_ACTION_GUEST_AUTH_TOTAL_HEIGHT,
    CART_ACTION_REVEAL_MS,
    CART_ACTION_CONTENT_REVEAL_DELAY_MS,
    CART_ACTION_SURFACE_BACKDROP_FILTER,
    CART_ACTION_SURFACE_BACKGROUND,
    CART_ACTION_SURFACE_FADE_MS,
    CART_ACTION_SURFACE_REVEAL_DELAY_MS,
} from '@/lib/cart/constants';
import { CartExpandedContent } from '@/components/cart/CartExpandedContent';
import { CartGuestAuthPrompt } from '@/components/cart/CartGuestAuthPrompt';
import { CartItemDetailsPopup } from '@/components/cart/CartItemDetailsPopup';
import { CartQuantityControl } from '@/components/cart/CartQuantityControl';
import { CartActionBarV2Collapsed } from '@/components/cart/CartActionBarV2Collapsed';
import { AuthPopup } from '@/components/auth/AuthPopup';

import { useCartActionBarController } from '@/hooks/cart/useCartActionBarController';

export const CartActionBar: React.FC<CartActionBarProps> = (props) => {
    const {
        showAddProductCard,
        collapsedVariant,
        liquidV2Shifted,
        disabled,
        onAdd,
        onEdit,
        onBuy,
        pathname,
        items,
        updateQuantity,
        isAuthenticated,
        totalQuantity,
        productsTotal,
        deliveryPrice,
        discount,
        grandTotal,
        deliveryMethod,
        setDeliveryMethod,
        paymentMethod,
        setPaymentMethod,
        isPaymentSubmitting,
        isCouponOpen,
        setIsCouponOpen,
        pendingCoupon,
        setPendingCoupon,
        appliedCoupon,
        setAppliedCoupon,
        isOfferAccepted,
        setIsOfferAccepted,
        isPolicyAccepted,
        setIsPolicyAccepted,
        isAuthPopupOpen,
        setIsAuthPopupOpen,
        handleExpandedPayment,
        isExpanded,
        isRendered,
        isAuthHydrated,
        agreementIdPrefix,
        collapsedPanelHeight,
        expandedPanelHeight,
        selectedDetailsItem,
        setSelectedDetailsItem,
        productPanelRef,
        expandedContentRef,
        handleZoneRef,
        isPanelDragActive,
        currentCartItem,
        displayTitle,
        displayColor,
        displayPrice,
        displayImage,
        shouldShowCartAction,
        panelDragHeight,
        expansionProgress,
        contentSwapProgress,
        collapsedContentProgress,
        expandedContentProgress,
        expandedSurfaceRevealProgress,
        footerRevealProgress,
        guestAuthRevealProgress,
        overlayRevealProgress,
        isPanelExpandedPresentation,
        isCompactCollapsedPresentation,
        setExpandedFromHandle,
        handleExpandedContentWheel,
        handleExpandedContentTouchStart,
        handleExpandedContentTouchEnd,
        handleHandlePointerDown,
        handleHandlePointerMove,
        handleHandlePointerUp,
        handleHandlePointerCancel,
        handleHandleClick,
        handleCollapsedPanelClick,
        handleCollapsedPanelClickCapture,
        handleCollapsedPanelPointerDown,
        handleCollapsedPanelPointerMove,
        handleCollapsedPanelPointerUp,
        handleCollapsedPanelPointerCancel,
        isCartActionVisible,
    } = useCartActionBarController(props);
    const isLiquidV2 = collapsedVariant === 'liquid-v2';

    if (!isRendered) return null;

    const renderExpandedContent = () => (
        <CartExpandedContent
            expandedContentRef={expandedContentRef}
            onWheel={handleExpandedContentWheel}
            onTouchStart={handleExpandedContentTouchStart}
            onTouchEnd={handleExpandedContentTouchEnd}
            deliveryMethod={deliveryMethod}
            setDeliveryMethod={setDeliveryMethod}
            paymentMethod={paymentMethod}
            setPaymentMethod={setPaymentMethod}
            showAddProductCard={showAddProductCard}
            displayTitle={displayTitle}
            displayColor={displayColor}
            displayPrice={displayPrice}
            displayImage={displayImage}
            currentCartItem={currentCartItem}
            disabled={disabled}
            onAdd={onAdd}
            onEdit={onEdit}
            onDetails={setSelectedDetailsItem}
            updateQuantity={updateQuantity}
            items={items}
            isCouponOpen={isCouponOpen}
            setIsCouponOpen={setIsCouponOpen}
            pendingCoupon={pendingCoupon}
            setPendingCoupon={setPendingCoupon}
            appliedCoupon={appliedCoupon}
            setAppliedCoupon={setAppliedCoupon}
            productsTotal={productsTotal}
            deliveryPrice={deliveryPrice}
            discount={discount}
            grandTotal={grandTotal}
            agreementIdPrefix={agreementIdPrefix}
            isOfferAccepted={isOfferAccepted}
            setIsOfferAccepted={setIsOfferAccepted}
            isPolicyAccepted={isPolicyAccepted}
            setIsPolicyAccepted={setIsPolicyAccepted}
        />
    );

    const shouldCollapseFromFooter = isPanelExpandedPresentation && !pathname?.startsWith('/product/');
    const cartActionSurfaceBackground = expandedSurfaceRevealProgress >= 1
        ? CART_ACTION_SURFACE_BACKGROUND
        : `rgb(255 255 255 / ${(expandedSurfaceRevealProgress * 70).toFixed(2)}%)`;
    const cartActionSurfaceBorderColor = `rgba(255, 255, 255, ${(expandedSurfaceRevealProgress * 0.3).toFixed(3)})`;
    const collapsedLayerBackground = `rgb(255 255 255 / ${(collapsedContentProgress * 40).toFixed(2)}%)`;
    const cartActionSurfaceBackdropProgress = isPanelExpandedPresentation ? expandedSurfaceRevealProgress : 0;
    const cartActionSurfaceBackdropFilter = isLiquidV2 || !isPanelExpandedPresentation
        ? 'none'
        : cartActionSurfaceBackdropProgress >= 1
            ? CART_ACTION_SURFACE_BACKDROP_FILTER
            : `blur(${(cartActionSurfaceBackdropProgress * 12).toFixed(2)}px) saturate(${(100 + cartActionSurfaceBackdropProgress * 60).toFixed(2)}%)`;
    const cartActionShellBottomLift = expansionProgress * CART_ACTION_EXPANDED_BOTTOM_LIFT;

    const handleOverlayPointerDown = (event: React.PointerEvent<HTMLButtonElement>) => {
        event.preventDefault();
        event.stopPropagation();
        setExpandedFromHandle(false);
    };

    return (
        <>
        <AuthPopup isOpen={isAuthPopupOpen} onClose={() => setIsAuthPopupOpen(false)} />
        {selectedDetailsItem ? (
            <CartItemDetailsPopup
                item={selectedDetailsItem}
                onClose={() => setSelectedDetailsItem(null)}
                onEdit={onEdit}
            />
        ) : null}
        <button
            type="button"
            className="cart-action-bar-overlay fixed inset-0 z-[101] appearance-none border-0 p-0 lg:hidden"
            aria-label="Свернуть корзину"
            aria-hidden={!isPanelExpandedPresentation}
            tabIndex={isExpanded ? 0 : -1}
            onPointerDown={handleOverlayPointerDown}
            onClick={() => setExpandedFromHandle(false)}
            style={{
                display: isLiquidV2 ? 'block' : undefined,
                background: '#000',
                opacity: overlayRevealProgress * 0.5,
                pointerEvents: isExpanded ? 'auto' : 'none',
                transition: isPanelDragActive
                    ? 'none'
                    : `opacity ${CART_ACTION_REVEAL_MS}ms cubic-bezier(0.22, 1, 0.36, 1)`,
                willChange: 'opacity',
            }}
        />
        <div
            className="cart-action-bar-shell fixed left-1/2 z-[102] lg:hidden"
            style={{
                display: isLiquidV2 ? 'block' : undefined,
                bottom: `calc(var(--cart-action-bar-bottom, 5px) + ${cartActionShellBottomLift.toFixed(2)}px)`,
                width: 'min(calc(100vw - 14px), 660px)',
                background: 'transparent',
                border: 0,
                borderRadius: 0,
                boxShadow: 'none',
                overflow: 'visible',
                transform: `translate3d(-50%, ${isCartActionVisible ? '0px' : '22px'}, 0)`,
                // Keep the glass surface at its final opacity from the first
                // rendered frame. Only the vertical position animates on
                // entry, so the page never shines through the cart first.
                opacity: shouldShowCartAction ? 1 : 0,
                pointerEvents: isCartActionVisible ? 'auto' : 'none',
                transition: isPanelDragActive
                    ? 'none'
                    : isCartActionVisible
                        ? `transform ${CART_ACTION_ENTER_MS}ms cubic-bezier(0.22, 1, 0.36, 1), bottom ${CART_ACTION_EXPAND_MS}ms cubic-bezier(0.22, 1, 0.36, 1)`
                        : `opacity ${CART_ACTION_EXIT_MS}ms ease, transform ${CART_ACTION_EXIT_MS}ms cubic-bezier(0.4, 0, 0.2, 1), bottom ${CART_ACTION_EXPAND_MS}ms cubic-bezier(0.22, 1, 0.36, 1)`,
            }}
        >
            {!isCompactCollapsedPresentation && !isPanelExpandedPresentation ? (
                <div
                    className="cart-action-bar-content-glow pointer-events-none absolute left-1/2 top-1/2 z-0"
                    style={{
                        width: '100vw',
                        height: CART_ACTION_CONTENT_GLOW_COLLAPSED_HEIGHT,
                        background: CART_ACTION_CONTENT_GLOW_COLLAPSED_GRADIENT,
                        transform: 'translateX(-50%) translateY(-50%)',
                        transition: 'height 0.3s ease',
                    }}
                />
            ) : null}

            <div
                className="cart-action-bar-content relative z-10 flex flex-col rounded-[20px] px-[clamp(5px,1.351vw,9px)]"
                style={{
                    overflow: isCompactCollapsedPresentation ? 'visible' : 'hidden',
                    backgroundColor: isLiquidV2
                        ? isPanelExpandedPresentation ? 'rgb(255 255 255 / 80%)' : 'transparent'
                        : isCompactCollapsedPresentation ? 'rgb(255 255 255 / 0%)' : cartActionSurfaceBackground,
                    border: `1px solid ${isCompactCollapsedPresentation ? 'transparent' : cartActionSurfaceBorderColor}`,
                    backdropFilter: cartActionSurfaceBackdropFilter,
                    WebkitBackdropFilter: cartActionSurfaceBackdropFilter,
                    boxShadow: isLiquidV2 || isCompactCollapsedPresentation
                        ? undefined
                        : 'rgba(0, 0, 0, 0.1) 0px 8px 32px, rgba(255, 255, 255, 0.5) 0px 1px 2px inset, rgba(255, 255, 255, 0.05) 0px -1px 2px inset',
                    transition: isPanelDragActive || isLiquidV2
                        ? 'none'
                        : [
                            `background-color ${CART_ACTION_SURFACE_FADE_MS}ms ease ${isPanelExpandedPresentation ? CART_ACTION_SURFACE_REVEAL_DELAY_MS : 0}ms`,
                            `border-color ${CART_ACTION_SURFACE_FADE_MS}ms ease ${isPanelExpandedPresentation ? CART_ACTION_SURFACE_REVEAL_DELAY_MS : 0}ms`,
                            `backdrop-filter ${CART_ACTION_SURFACE_FADE_MS}ms ease ${isPanelExpandedPresentation ? CART_ACTION_SURFACE_REVEAL_DELAY_MS : 0}ms`,
                            `-webkit-backdrop-filter ${CART_ACTION_SURFACE_FADE_MS}ms ease ${isPanelExpandedPresentation ? CART_ACTION_SURFACE_REVEAL_DELAY_MS : 0}ms`,
                        ].join(', '),
                }}
            >
                {isPanelExpandedPresentation ? (
                    <div
                        className="cart-action-bar-content-glow pointer-events-none absolute bottom-[-30px] left-0 z-0"
                        style={{
                            width: '100%',
                            height: CART_ACTION_CONTENT_GLOW_EXPANDED_HEIGHT,
                            background: CART_ACTION_CONTENT_GLOW_EXPANDED_GRADIENT,
                            opacity: isLiquidV2 ? 0.74 : 1,
                        }}
                    />
                ) : null}

                {/* ═══ Handle zone — draggable ═══ */}
                <div
                    className="relative z-10 flex flex-col items-center select-none"
                    style={{ paddingTop: 5, paddingBottom: 0 }}
                >
                    <span
                        className="cart-action-bar-handle h-[2px] w-[50px] shrink-0 rounded-[15px] shadow-[inset_0_0.5px_0.5px_rgba(0,0,0,0.25)]"
                        style={{
                            height: isLiquidV2 ? 3 : 2,
                            background: isLiquidV2
                                ? '#D5D5D5'
                                : isPanelExpandedPresentation ? '#A2A2A2' : '#D5D5D5',
                            boxShadow: '0 0.5px 0.5px 0 rgba(0, 0, 0, 0.25) inset',
                        }}
                    />

                    {collapsedVariant === 'legacy' && !isPanelExpandedPresentation && totalQuantity > 0 ? (
                        <span className="mt-[2px] h-[10px] w-full pr-[25px] text-right font-manrope text-[10px] font-normal leading-[10px] text-[#9F9F9F]">
                            {`в корзине: ${totalQuantity}`}
                        </span>
                    ) : (
                        <span className="pointer-events-none h-[7px] shrink-0" aria-hidden="true" />
                    )}
                    <button
                        ref={handleZoneRef}
                        type="button"
                        aria-expanded={isExpanded}
                        aria-label="Открыть корзину"
                        className="cart-action-bar-handle-zone absolute left-0 right-0 top-0 z-10 h-[36px] cursor-pointer appearance-none border-0 bg-transparent p-0 text-[1px] text-[#545454] opacity-[0.01]"
                        style={{ touchAction: 'none' }}
                        onPointerDown={handleHandlePointerDown}
                        onPointerMove={handleHandlePointerMove}
                        onPointerUp={handleHandlePointerUp}
                        onPointerCancel={handleHandlePointerCancel}
                        onClick={handleHandleClick}
                    >
                        Открыть корзину
                    </button>
                </div>

                {/* ═══ Product panel (collapsed) / Full cart (expanded) ═══ */}
                <div
                    ref={productPanelRef}
                    className="cart-action-bar-product-panel relative z-10 mt-[clamp(4px,1.081vw,7px)] flex min-h-0 shrink-0 items-start overflow-hidden rounded-[15px]"
                    onClickCapture={handleCollapsedPanelClickCapture}
                    onClick={handleCollapsedPanelClick}
                    onPointerDown={handleCollapsedPanelPointerDown}
                    onPointerMove={handleCollapsedPanelPointerMove}
                    onPointerUp={handleCollapsedPanelPointerUp}
                    onPointerCancel={handleCollapsedPanelPointerCancel}
                    style={{
                        height: panelDragHeight
                            ? panelDragHeight
                            : isExpanded
                                ? `${expandedPanelHeight}px`
                                : `${collapsedPanelHeight}px`,
                        padding: 0,
                        background: 'transparent',
                        border: '1px solid',
                        borderColor: isCompactCollapsedPresentation
                            ? 'rgba(255, 255, 255, 0.3)'
                            : '#D9D9D9',
                        boxShadow: isCompactCollapsedPresentation
                            ? '0 0 16px 3px rgba(255, 255, 255, 0.82), 0 2px 5px 0 rgba(0, 0, 0, 0.25) inset'
                            : '0 2px 5px 0 rgba(0, 0, 0, 0.25) inset',
                        backdropFilter: isCompactCollapsedPresentation ? 'blur(12px) saturate(160%)' : 'blur(0px) saturate(100%)',
                        WebkitBackdropFilter: isCompactCollapsedPresentation ? 'blur(12px) saturate(160%)' : 'blur(0px) saturate(100%)',
                        ...(isLiquidV2 ? {
                            boxShadow: 'none',
                            backdropFilter: 'none',
                            WebkitBackdropFilter: 'none',
                            ...(!isPanelExpandedPresentation ? {
                                borderColor: 'transparent',
                            } : {}),
                        } : {}),
                        transition: isPanelDragActive
                            ? 'none'
                            : isLiquidV2
                                ? [
                                    `height ${CART_ACTION_EXPAND_MS}ms cubic-bezier(0.32, 0.72, 0, 1)`,
                                    `border-color ${CART_ACTION_REVEAL_MS}ms ease`,
                                ].join(', ')
                                : [
                                `height ${CART_ACTION_EXPAND_MS}ms cubic-bezier(0.22, 1, 0.36, 1)`,
                                `border-color ${CART_ACTION_REVEAL_MS}ms ease`,
                                `box-shadow ${CART_ACTION_REVEAL_MS}ms ease`,
                                `backdrop-filter ${CART_ACTION_REVEAL_MS}ms ease`,
                                `-webkit-backdrop-filter ${CART_ACTION_REVEAL_MS}ms ease`,
                            ].join(', '),
                        willChange: isExpanded || isPanelDragActive ? 'height' : 'auto',
                        contain: 'layout paint',
                        transform: 'translateZ(0)',
                        overflowY: 'hidden',
                        touchAction: isExpanded ? 'pan-y' : 'pan-x',
                    }}
                >
                    <div
                        className="cart-action-bar-collapsed-layer absolute left-0 right-0 top-0 z-[1] flex items-start"
                        aria-hidden={expansionProgress >= 0.5}
                        style={{
                            boxSizing: 'border-box',
                            height: `${collapsedPanelHeight}px`,
                            padding: 'clamp(10px, 2.703vw, 17px) clamp(20px, 5.405vw, 35px)',
                            backgroundColor: collapsedLayerBackground,
                            ...(isLiquidV2 ? {
                                padding: 0,
                                backgroundColor: 'transparent',
                            } : {}),
                            opacity: collapsedContentProgress,
                            transform: `translate3d(0, ${Math.round(contentSwapProgress * -8)}px, 0)`,
                            pointerEvents: expansionProgress > 0.001 ? 'none' : 'auto',
                            transition: isPanelDragActive
                                ? 'none'
                                : [
                                    `opacity ${CART_ACTION_REVEAL_MS}ms ease ${isPanelExpandedPresentation ? CART_ACTION_CONTENT_REVEAL_DELAY_MS : 0}ms`,
                                    `transform ${CART_ACTION_REVEAL_MS}ms cubic-bezier(0.22, 1, 0.36, 1) ${isPanelExpandedPresentation ? CART_ACTION_CONTENT_REVEAL_DELAY_MS : 0}ms`,
                                    `background-color ${CART_ACTION_REVEAL_MS}ms ease ${isPanelExpandedPresentation ? CART_ACTION_CONTENT_REVEAL_DELAY_MS : 0}ms`,
                                ].join(', '),
                        }}
                    >
                        {isLiquidV2 ? (
                            <CartActionBarV2Collapsed
                                isAuthenticated={isAuthenticated}
                                shifted={liquidV2Shifted}
                                totalQuantity={totalQuantity}
                                onLogin={props.onLogin ?? (() => setIsAuthPopupOpen(true))}
                                onOpen={() => setExpandedFromHandle(true)}
                            />
                        ) : (
                        <div className="cart-action-bar-product-row flex w-full items-center justify-between gap-[clamp(30px,8.108vw,52px)]">
                            <button
                                type="button"
                                className="cart-action-bar-product-summary flex min-w-0 flex-1 flex-col border-0 bg-transparent p-0 text-left font-manrope text-[12px] font-normal leading-normal text-[#2D2D2D]"
                                aria-label="Раскрыть корзину"
                                onClick={() => setExpandedFromHandle(true)}
                            >
                                <div className="truncate leading-[12px]">{displayTitle}</div>
                                <div className="cart-action-bar-product-meta flex items-center justify-between gap-[8px] text-[10px] leading-[10px]">
                                    <span className="min-w-0 truncate">Цвет: {displayColor || '—'}</span>
                                    <span className="whitespace-nowrap">{displayPrice.toLocaleString('ru-RU')} ₽</span>
                                </div>
                            </button>

                            {currentCartItem ? (
                                <CartQuantityControl item={currentCartItem} updateQuantity={updateQuantity} variant="collapsed" />
                            ) : (
                                <button
                                    type="button"
                                    onClick={onAdd}
                                    disabled={disabled}
                                    className="cart-action-bar-add flex h-[clamp(27px,7.297vw,47px)] w-[clamp(135px,36.486vw,234px)] shrink-0 items-center justify-center rounded-[5px] font-manrope text-[35px] font-light leading-none text-[#777777] transition active:translate-y-px disabled:opacity-45"
                                    style={{
                                        background: 'rgba(255, 255, 255, 0.6)',
                                        border: '1px solid #E5E5E5',
                                        boxShadow: '0 1px 1.8px 0 rgba(0, 0, 0, 0.26)',
                                    }}
                                    aria-label="Добавить в корзину"
                                >
                                    <span className="mb-[4px]">+</span>
                                </button>
                            )}
                        </div>
                        )}
                    </div>
                    <div
                        className="cart-action-bar-expanded-layer absolute left-0 right-0 top-0 z-[1]"
                        aria-hidden={!isPanelExpandedPresentation}
                        style={{
                            height: `${expandedPanelHeight}px`,
                            opacity: expandedContentProgress,
                            transform: `translate3d(0, ${Math.round((1 - contentSwapProgress) * 12)}px, 0)`,
                            visibility: isPanelExpandedPresentation ? 'visible' : 'hidden',
                            pointerEvents: isExpanded ? 'auto' : 'none',
                            transition: isPanelDragActive
                                ? 'none'
                                : [
                                    `opacity ${CART_ACTION_REVEAL_MS}ms ease ${isPanelExpandedPresentation ? CART_ACTION_CONTENT_REVEAL_DELAY_MS : 0}ms`,
                                    `transform ${CART_ACTION_EXPAND_MS}ms cubic-bezier(0.22, 1, 0.36, 1) ${isPanelExpandedPresentation ? CART_ACTION_CONTENT_REVEAL_DELAY_MS : 0}ms`,
                                ].join(', '),
                        }}
                    >
                        {renderExpandedContent()}
                    </div>
                </div>

                {/* ═══ Footer buttons ═══ */}
                <div
                    className="cart-action-bar-footer-reveal shrink-0 overflow-hidden"
                    aria-hidden={footerRevealProgress <= 0.001}
                    style={{
                        maxHeight: `${30 * footerRevealProgress}px`,
                        opacity: footerRevealProgress,
                        pointerEvents: footerRevealProgress >= 0.999 ? 'auto' : 'none',
                        transition: isPanelDragActive
                            ? 'none'
                            : `max-height ${CART_ACTION_EXPAND_MS}ms cubic-bezier(0.22, 1, 0.36, 1), opacity ${CART_ACTION_REVEAL_MS}ms ease`,
                    }}
                >
                    <div
                        className="cart-action-bar-footer relative z-10 mb-[7px] grid h-[14px] shrink-0 grid-cols-[1fr_auto_1fr] items-center"
                        style={{ marginTop: '9px' }}
                    >
                        <button
                            type="button"
                            onClick={shouldCollapseFromFooter ? () => setExpandedFromHandle(false) : onEdit}
                            aria-label={shouldCollapseFromFooter ? 'Свернуть корзину' : 'Изменить товар'}
                            className="flex h-[14px] items-center justify-center gap-[10px] font-manrope text-[14px] font-semibold leading-[11.582px] text-[#676767]"
                        >
                            {shouldCollapseFromFooter ? (
                                <Image
                                    src="/back_icon_item.svg"
                                    alt=""
                                    width={18}
                                    height={11}
                                    aria-hidden="true"
                                    className="h-[11px] w-[18px] object-contain"
                                />
                            ) : (
                                <Image
                                    src="/edit_icon.svg"
                                    alt=""
                                    width={11}
                                    height={11}
                                    aria-hidden="true"
                                    className="cart-action-bar-edit-icon h-[11px] w-[11px]"
                                />
                            )}
                            <span>{shouldCollapseFromFooter ? 'НАЗАД' : 'ИЗМЕНИТЬ'}</span>
                        </button>

                        <div
                            className="rounded-[15px]"
                            style={{
                                width: '2px',
                                height: '14px',
                                background: '#9D9D9D',
                                boxShadow: '0 0.5px 0.5px 0 rgba(0, 0, 0, 0.25) inset',
                            }}
                        />

                        <button
                            type="button"
                            onClick={isPanelExpandedPresentation ? handleExpandedPayment : onBuy}
                            disabled={isPanelExpandedPresentation && (isPaymentSubmitting || !isOfferAccepted || !isPolicyAccepted || items.length === 0)}
                            aria-busy={isPanelExpandedPresentation && isPaymentSubmitting}
                            className="flex h-[14px] items-center justify-center font-manrope text-[14px] font-semibold leading-[11.582px] text-[#676767] transition-opacity disabled:opacity-40"
                        >
                            {isPanelExpandedPresentation
                                ? isPaymentSubmitting ? 'ОБРАБОТКА...' : 'ОПЛАТИТЬ'
                                : 'КУПИТЬ'}
                        </button>
                    </div>
                </div>
            </div>

            {isAuthHydrated && !isAuthenticated ? (
                <div
                    className="cart-action-bar-guest-auth-reveal overflow-visible"
                    aria-hidden={guestAuthRevealProgress <= 0.001}
                    style={{
                        maxHeight: `${CART_ACTION_GUEST_AUTH_TOTAL_HEIGHT * guestAuthRevealProgress}px`,
                        opacity: guestAuthRevealProgress,
                        transform: `translate3d(0, ${Math.round((1 - guestAuthRevealProgress) * 10)}px, 0)`,
                        pointerEvents: isExpanded && guestAuthRevealProgress >= 0.999 ? 'auto' : 'none',
                        transition: isPanelDragActive
                            ? 'none'
                            : `max-height ${CART_ACTION_EXPAND_MS}ms cubic-bezier(0.22, 1, 0.36, 1), opacity ${CART_ACTION_REVEAL_MS}ms ease, transform ${CART_ACTION_EXPAND_MS}ms cubic-bezier(0.22, 1, 0.36, 1)`,
                    }}
                >
                    <CartGuestAuthPrompt onLogin={() => setIsAuthPopupOpen(true)} />
                </div>
            ) : null}
        </div>
        </>
    );
};
