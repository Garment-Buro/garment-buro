import Image from 'next/image';
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

import { AppIcon } from '@/components/icons/AppIcon';
import { CartAddProductCard } from './CartAddProductCard';
import { CartChoiceOption } from './CartChoiceOption';
import {
    CartCouponSection,
    CartGrandTotalSection,
    CartTotalsSection,
} from './CartCheckoutSections';
import { CartItemRow } from './CartItemRow';

const ChevronRight = () => (
    <svg width="8" height="9" viewBox="0 0 8 9" fill="none" style={{ width: 6.5, height: 7.5 }}>
        <path d="M0.5 0.5L7 4.25391L0.5 8.00668" stroke="#2D2D2D" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

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
        <div
            className="flex w-full flex-col"
            style={{
                width: '100%',
                padding: 'clamp(20px, 5.405vw, 35px) 5px clamp(10px, 2.703vw, 17px)',
                background: CART_ACTION_PRODUCT_SECTION_BACKGROUND,
            }}
        >
            <div
                className="flex flex-col"
                style={{ paddingInline: 'max(0px, calc(clamp(10px, 2.703vw, 17px) - 5px))' }}
            >
                <div className="flex items-center justify-between" style={{ padding: '0 clamp(30px, 8.108vw, 52px) 0 clamp(10px, 2.703vw, 17px)' }}>
                    <div className="flex gap-[7px]" style={{ alignItems: 'self-end' }}>
                        <AppIcon name="map-pin" width={10} height={12} className="shrink-0 text-[#2D2D2D]" style={{ width: 10, height: 12 }} />
                        <Image src="/cdek icon.svg" alt="СДЭК" width={36} height={10} className="shrink-0" style={{ width: 36, height: 10 }} />
                    </div>
                    <ChevronRight />
                </div>
                <div style={{ paddingLeft: 'clamp(25px, 6.757vw, 43px)', marginTop: 'clamp(5px, 1.351vw, 9px)', maxWidth: '72%' }}>
                    <span style={{
                        display: 'block',
                        color: '#2D2D2D',
                        fontFamily: 'var(--font-manrope), Manrope, sans-serif',
                        fontSize: 10,
                        fontWeight: 500,
                        lineHeight: 'normal',
                    }}>
                        Россия, г. Москва, пункт выдачи СДЭК, ул. Беговая, 38/1, 170007
                    </span>
                </div>
            </div>
            <div className="flex justify-between" style={{ marginTop: 'clamp(10px, 2.703vw, 17px)', gap: 'clamp(3px, 0.811vw, 5px)' }}>
                <CartChoiceOption
                    variant="delivery"
                    active={deliveryMethod === 'pickup'}
                    onSelect={() => setDeliveryMethod('pickup')}
                    label="Доставка в пункт выдачи"
                    primary="Бесплатно"
                    secondary="8 мая - 12 мая"
                />
                <CartChoiceOption
                    variant="delivery"
                    active={deliveryMethod === 'courier'}
                    onSelect={() => setDeliveryMethod('courier')}
                    label="Доставка курьером"
                    primary="547 ₽"
                    secondary="4 мая - 8 мая"
                />
            </div>
        </div>

        <ExpandedCartSeparator />

        <div
            className="flex w-full flex-col"
            style={{
                width: '100%',
                padding: 'clamp(10px, 2.703vw, 17px) clamp(10px, 2.703vw, 17px) clamp(13px, 3.514vw, 22px)',
                background: CART_ACTION_PRODUCT_SECTION_BACKGROUND,
            }}
        >
            <div className="flex items-center justify-between" style={{ padding: '0 clamp(30px, 8.108vw, 52px) 0 clamp(10px, 2.703vw, 17px)' }}>
                <div className="flex gap-[7px]" style={{ alignItems: 'self-end' }}>
                    <AppIcon name="customer" width={12} height={14} className="shrink-0 text-[#2D2D2D]" style={{ width: 12, height: 14 }} />
                    <span style={{
                        color: '#2D2D2D',
                        fontFamily: 'var(--font-manrope), Manrope, sans-serif',
                        fontSize: 12,
                        fontWeight: 700,
                        lineHeight: 'normal',
                    }}>
                        Получатель
                    </span>
                </div>
                <ChevronRight />
            </div>
            <div style={{ paddingLeft: 'clamp(25px, 6.757vw, 43px)' }}>
                <span style={{
                    color: '#2D2D2D',
                    fontFamily: 'var(--font-manrope), Manrope, sans-serif',
                    fontSize: 10,
                    fontWeight: 500,
                    lineHeight: 'normal',
                }}>
                    Клочинский Константин, +7 900 200-00-11
                </span>
            </div>
        </div>

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
