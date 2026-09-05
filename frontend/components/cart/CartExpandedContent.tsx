import type {
    Dispatch,
    RefObject,
    SetStateAction,
    TouchEventHandler,
    WheelEventHandler,
} from 'react';

import type { CartActionCoupon, CartDeliveryMethod, CartPaymentMethod } from '@/lib/cart/actionTypes';
import {
    CART_ACTION_PRODUCT_SECTION_BACKGROUND,
    CART_ACTION_SECTION_GAP_BACKGROUND,
} from '@/lib/cart/constants';
import type { CartItem } from '@/lib/cart/types';

import { CartDeliveryDetails } from '@/components/checkout/CartDeliveryDetails';
import { CartAddProductCard } from './CartAddProductCard';
import {
    CartCouponSection,
    CartGrandTotalSection,
    CartTotalsSection,
} from './CartCheckoutSections';
import { CartItemRow } from './CartItemRow';

const ExpandedCartSeparator = () => (
    <div
        className="cart-action-bar-section-separator w-full shrink-0"
        aria-hidden="true"
        style={{
            height: 'clamp(8px, 2.162vw, 14px)',
            background: CART_ACTION_SECTION_GAP_BACKGROUND,
        }}
    />
);

type CartExpandedContentProps = {
    expandedContentRef: RefObject<HTMLDivElement | null>;
    onWheel: WheelEventHandler<HTMLDivElement>;
    onTouchStart: TouchEventHandler<HTMLDivElement>;
    onTouchEnd: TouchEventHandler<HTMLDivElement>;
    deliveryMethod: CartDeliveryMethod;
    setDeliveryMethod: Dispatch<SetStateAction<CartDeliveryMethod>>;
    paymentMethod: CartPaymentMethod;
    setPaymentMethod: Dispatch<SetStateAction<CartPaymentMethod>>;
    showAddProductCard: boolean;
    displayTitle: string;
    displayColor: string;
    displayPrice: number;
    displayImage: string;
    currentCartItem?: CartItem;
    disabled: boolean;
    onAdd: () => void;
    onEdit: () => void;
    onDetails: (item: CartItem | null) => void;
    updateQuantity: (id: string, quantity: number) => void;
    items: CartItem[];
    isCouponOpen: boolean;
    setIsCouponOpen: Dispatch<SetStateAction<boolean>>;
    pendingCoupon: CartActionCoupon | null;
    setPendingCoupon: Dispatch<SetStateAction<CartActionCoupon | null>>;
    appliedCoupon: CartActionCoupon | null;
    setAppliedCoupon: Dispatch<SetStateAction<CartActionCoupon | null>>;
    productsTotal: number;
    deliveryPrice: number;
    checkoutError: string;
    retryQuote: () => void;
    quoteLoading: boolean;
    deliveryQuoted: boolean;
    discount: number;
    grandTotal: number;
    agreementIdPrefix: string;
    isOfferAccepted: boolean;
    setIsOfferAccepted: Dispatch<SetStateAction<boolean>>;
    isPolicyAccepted: boolean;
    setIsPolicyAccepted: Dispatch<SetStateAction<boolean>>;
};

export const CartExpandedContent = ({
    expandedContentRef,
    onWheel,
    onTouchStart,
    onTouchEnd,
    deliveryMethod,
    setDeliveryMethod,
    paymentMethod,
    setPaymentMethod,
    showAddProductCard,
    displayTitle,
    displayColor,
    displayPrice,
    displayImage,
    currentCartItem,
    disabled,
    onAdd,
    onEdit,
    onDetails,
    updateQuantity,
    items,
    isCouponOpen,
    setIsCouponOpen,
    pendingCoupon,
    setPendingCoupon,
    appliedCoupon,
    setAppliedCoupon,
    productsTotal,
    deliveryPrice,
    checkoutError,
    retryQuote,
    quoteLoading,
    deliveryQuoted,
    discount,
    grandTotal,
    agreementIdPrefix,
    isOfferAccepted,
    setIsOfferAccepted,
    isPolicyAccepted,
    setIsPolicyAccepted,
}: CartExpandedContentProps) => (
    <div
        ref={expandedContentRef}
        className="flex h-full w-full flex-col overflow-y-auto"
        onWheel={onWheel}
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
        onTouchCancel={onTouchEnd}
        style={{
            height: '100%',
            maxHeight: '100%',
            WebkitOverflowScrolling: 'touch',
            overscrollBehaviorY: 'contain',
            touchAction: 'pan-y',
        }}
    >
        <CartDeliveryDetails method={deliveryMethod} onChange={setDeliveryMethod} />
        {checkoutError && <p role="alert" className="px-6 py-3 text-sm text-red-800">{checkoutError}</p>}
        {!deliveryQuoted && items.length > 0 && <button type="button" disabled={quoteLoading} onClick={retryQuote} className="px-6 py-3 text-left text-sm underline disabled:opacity-50">{quoteLoading ? 'Рассчитываем доставку…' : 'Рассчитать доставку'}</button>}

        {showAddProductCard ? (
            <>
                <ExpandedCartSeparator />
                <CartAddProductCard
                    title={displayTitle}
                    color={displayColor}
                    price={displayPrice}
                    image={displayImage}
                    item={currentCartItem}
                    disabled={disabled}
                    onAdd={onAdd}
                    onEdit={onEdit}
                    onDetails={onDetails}
                    updateQuantity={updateQuantity}
                />
            </>
        ) : null}
        {items.length > 0 ? (
            <>
                <ExpandedCartSeparator />
                <section
                    className="cart-action-bar-expanded-cart-items flex w-full flex-col gap-[clamp(16px,4.324vw,28px)] px-[clamp(22px,5.946vw,38px)] py-[clamp(16px,4.324vw,28px)]"
                    style={{ background: CART_ACTION_PRODUCT_SECTION_BACKGROUND }}
                >
                    <div className="font-manrope text-[12px] font-bold leading-normal text-[#2D2D2D]">Корзина</div>
                    <div className="flex flex-col gap-[clamp(16px,4.324vw,28px)]">
                        {items.map(item => (
                            <CartItemRow
                                key={item.id}
                                item={item}
                                onEdit={onEdit}
                                onDetails={onDetails}
                                updateQuantity={updateQuantity}
                            />
                        ))}
                    </div>
                </section>
            </>
        ) : null}

        <ExpandedCartSeparator />
        <CartCouponSection
            isOpen={isCouponOpen}
            pendingCoupon={pendingCoupon}
            setIsOpen={setIsCouponOpen}
            setPendingCoupon={setPendingCoupon}
            setAppliedCoupon={setAppliedCoupon}
        />
        <ExpandedCartSeparator />
        <CartTotalsSection
            deliveryLabel={quoteLoading ? 'Рассчитываем…' : !deliveryQuoted ? 'После выбора адреса' : undefined}
            productsTotal={productsTotal}
            deliveryPrice={deliveryPrice}
            appliedCoupon={appliedCoupon}
            discount={discount}
        />
        <ExpandedCartSeparator />
        <CartGrandTotalSection
            paymentMethod={paymentMethod}
            setPaymentMethod={setPaymentMethod}
            grandTotal={grandTotal}
            agreementIdPrefix={agreementIdPrefix}
            isOfferAccepted={isOfferAccepted}
            setIsOfferAccepted={setIsOfferAccepted}
            isPolicyAccepted={isPolicyAccepted}
            setIsPolicyAccepted={setIsPolicyAccepted}
        />
    </div>
);
