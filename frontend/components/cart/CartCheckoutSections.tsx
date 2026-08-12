import Image from 'next/image';
import { AppIcon } from '@/components/icons/AppIcon';
import type { Dispatch, ReactNode, SetStateAction } from 'react';

import type { CartActionCoupon, CartPaymentMethod } from '@/lib/cart/actionTypes';
import {
    CART_ACTION_COUPON_BUTTON_SHADOW,
    CART_ACTION_COUPONS,
    CART_ACTION_PRODUCT_SECTION_BACKGROUND,
} from '@/lib/cart/constants';
import { formatCartPrice } from '@/lib/cart/utils/cartAction';

import { CartChoiceOption } from './CartChoiceOption';

type CartCouponSectionProps = {
    isOpen: boolean;
    pendingCoupon: CartActionCoupon | null;
    setIsOpen: Dispatch<SetStateAction<boolean>>;
    setPendingCoupon: Dispatch<SetStateAction<CartActionCoupon | null>>;
    setAppliedCoupon: Dispatch<SetStateAction<CartActionCoupon | null>>;
};

export const CartCouponSection = ({
    isOpen,
    pendingCoupon,
    setIsOpen,
    setPendingCoupon,
    setAppliedCoupon,
}: CartCouponSectionProps) => {
    const couponButtonLabel = pendingCoupon
        ? `Скидка на ${pendingCoupon.label.toLowerCase()} — ${pendingCoupon.amount}`
        : 'Выберите купон';

    const renderCouponTicket = (coupon: CartActionCoupon) => {
        const isSelected = pendingCoupon?.value === coupon.value;

        return (
            <button
                key={coupon.value}
                type="button"
                className="relative grid h-[clamp(41px,11.081vw,71px)] w-full grid-cols-[clamp(76px,20.541vw,131px)_minmax(0,1fr)] items-center overflow-hidden rounded-[4px] text-left font-manrope text-[#2D2D2D]"
                style={{
                    backgroundImage: `url(${isSelected ? '/used_sell.webp' : '/unused_sell.webp'})`,
                    backgroundRepeat: 'no-repeat',
                    backgroundSize: '100% 100%',
                }}
                onClick={() => {
                    setPendingCoupon(coupon);
                    setIsOpen(false);
                }}
            >
                <span className="flex h-full items-center justify-center border-r border-dotted border-[#C7C7C7] text-[15px] font-extrabold">
                    {coupon.amount}
                </span>
                <span className="px-[18px] text-[10px] font-medium">{coupon.label}</span>
            </button>
        );
    };

    return (
        <section
            className="cart-action-bar-coupon-section relative overflow-visible px-[clamp(22px,5.946vw,38px)] py-[clamp(14px,3.784vw,24px)]"
            style={{ background: CART_ACTION_PRODUCT_SECTION_BACKGROUND }}
        >
            <div className="font-manrope text-[12px] font-bold leading-normal text-[#2D2D2D]">Купон</div>
            <div className="mt-[clamp(10px,2.703vw,17px)] grid w-full grid-cols-[minmax(0,1fr)_clamp(75px,20.27vw,130px)] gap-[clamp(11px,2.973vw,19px)]">
                <button
                    type="button"
                    className="grid h-[clamp(25px,6.757vw,43px)] min-w-0 grid-cols-[clamp(32px,8.649vw,55px)_minmax(0,1fr)_clamp(22px,5.946vw,38px)] items-center rounded-[3px] bg-white font-manrope text-[10px] font-medium text-[#2D2D2D]"
                    style={{ boxShadow: CART_ACTION_COUPON_BUTTON_SHADOW }}
                    onClick={() => setIsOpen(current => !current)}
                    aria-expanded={isOpen}
                >
                    <span className="flex items-center justify-center">
                        <Image
                            src="/discount_header_icon.svg"
                            alt=""
                            width={18}
                            height={13}
                            aria-hidden="true"
                            className="h-[13px] w-[18px] object-contain"
                        />
                    </span>
                    <span className="truncate text-left">{couponButtonLabel}</span>
                    <span className="flex items-center justify-center" aria-hidden="true">
                        <AppIcon
                            name="arrow-up"
                            width={8}
                            height={7}
                            className={`h-[7px] w-[8px] text-[#2D2D2D] transition-transform ${isOpen ? '' : 'rotate-180'}`}
                        />
                    </span>
                </button>
                <button
                    type="button"
                    className="h-[clamp(25px,6.757vw,43px)] rounded-[3px] border border-[#E5E5E5] bg-[rgba(255,255,255,0.6)] font-manrope text-[10px] font-medium text-[#2D2D2D]"
                    style={{ boxShadow: CART_ACTION_COUPON_BUTTON_SHADOW }}
                    disabled={!pendingCoupon}
                    onClick={() => {
                        setAppliedCoupon(pendingCoupon);
                        setIsOpen(false);
                    }}
                >
                    Применить
                </button>
            </div>
            {isOpen && (
                <div
                    className="cart-action-bar-coupon-dropdown absolute left-[clamp(22px,5.946vw,38px)] top-[calc(clamp(64px,17.297vw,111px)+5px)] z-[40] flex h-[clamp(130px,35.135vw,225px)] w-[clamp(230px,62.162vw,398px)] flex-col gap-[0px] rounded-[5px] bg-white p-[3px]"
                    style={{ boxShadow: '0 2px 4px 0 rgba(0, 0, 0, 0.25)' }}
                >
                    {CART_ACTION_COUPONS.map(renderCouponTicket)}
                </div>
            )}
        </section>
    );
};

type CartTotalsSectionProps = {
    productsTotal: number;
    deliveryPrice: number;
    appliedCoupon: CartActionCoupon | null;
    discount: number;
};

export const CartTotalsSection = ({
    productsTotal,
    deliveryPrice,
    appliedCoupon,
    discount,
}: CartTotalsSectionProps) => (
    <section
        className="cart-action-bar-totals-section px-[clamp(28px,7.568vw,48px)] py-[clamp(14px,3.784vw,24px)]"
        style={{ background: CART_ACTION_PRODUCT_SECTION_BACKGROUND }}
    >
        <div className="flex flex-col gap-[0px] font-manrope text-[10px] font-medium leading-normal text-[#2D2D2D]">
            <div className="flex justify-between">
                <span>Товары</span>
                <span>{formatCartPrice(productsTotal)}</span>
            </div>
            <div className="flex justify-between">
                <span>Доставка</span>
                <span>{deliveryPrice > 0 ? formatCartPrice(deliveryPrice) : 'Бесплатно'}</span>
            </div>
            {appliedCoupon ? (
                <div className="flex justify-between text-[#45F472]">
                    <span>Скидка</span>
                    <span>{discount > 0 ? `-${formatCartPrice(discount)}` : '0 ₽'}</span>
                </div>
            ) : null}
        </div>
    </section>
);

const PaymentCardIcon = () => (
    <svg aria-hidden="true" width="12" height="14" viewBox="0 0 24 24" fill="none" className="shrink-0">
        <rect x="3" y="6" width="18" height="13" rx="2" stroke="#000000" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M3 10H20.5" stroke="#000000" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M7 15H9" stroke="#000000" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

const renderAgreementCheckbox = ({
    id,
    checked,
    onToggle,
    children,
}: {
    id: string;
    checked: boolean;
    onToggle: (checked: boolean) => void;
    children: ReactNode;
}) => (
    <div className="cart-action-bar-agreement-checkbox flex min-h-[32px] items-center gap-[7px] text-left">
        <div className="relative flex h-[28px] w-[28px] shrink-0 items-center justify-center">
            <input
                type="checkbox"
                id={id}
                checked={checked}
                onChange={(event) => onToggle(event.currentTarget.checked)}
                className="peer m-0 block h-[28px] w-[28px] shrink-0 appearance-none rounded-[5px] border border-[#818181] bg-transparent p-0 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-[#818181]"
            />
            <div className="pointer-events-none absolute left-1/2 top-1/2 h-[11px] w-[11px] -translate-x-1/2 -translate-y-1/2 text-[#818181] opacity-0 peer-checked:opacity-100">
                <svg aria-hidden="true" width="11" height="11" viewBox="0 0 512 512" fill="currentColor" className="block h-[11px] w-[11px]">
                    <path d="M173.898 439.404l-166.4-166.4c-9.997-9.997-9.997-26.206 0-36.204l36.203-36.204c9.997-9.998 26.207-9.998 36.204 0L192 312.69 432.095 72.596c9.997-9.997 26.207-9.997 36.204 0l36.203 36.204c9.997 9.997 9.997 26.206 0 36.204l-294.4 294.401c-9.998 9.997-26.207 9.997-36.204-.001z" />
                </svg>
            </div>
        </div>
        <label htmlFor={id} className="cursor-pointer font-manrope text-[10px] font-normal leading-normal text-[#666666]">
            {children}
        </label>
    </div>
);

type CartGrandTotalSectionProps = {
    paymentMethod: CartPaymentMethod;
    setPaymentMethod: Dispatch<SetStateAction<CartPaymentMethod>>;
    grandTotal: number;
    agreementIdPrefix: string;
    isOfferAccepted: boolean;
    setIsOfferAccepted: Dispatch<SetStateAction<boolean>>;
    isPolicyAccepted: boolean;
    setIsPolicyAccepted: Dispatch<SetStateAction<boolean>>;
};

export const CartGrandTotalSection = ({
    paymentMethod,
    setPaymentMethod,
    grandTotal,
    agreementIdPrefix,
    isOfferAccepted,
    setIsOfferAccepted,
    isPolicyAccepted,
    setIsPolicyAccepted,
}: CartGrandTotalSectionProps) => (
    <section
        className="cart-action-bar-grand-total-section px-[5px] py-[clamp(14px,3.784vw,24px)]"
        style={{ background: CART_ACTION_PRODUCT_SECTION_BACKGROUND }}
    >
        <div className="cart-action-bar-payment-method mb-[clamp(14px,3.784vw,24px)] font-manrope">
            <div
                className="flex flex-col"
                style={{ paddingInline: 'max(0px, calc(clamp(28px, 7.568vw, 48px) - 5px))' }}
            >
                <div
                    className="mb-[clamp(7px,1.892vw,12px)] flex gap-[7px]"
                    style={{ alignItems: 'self-end' }}
                >
                    <PaymentCardIcon />
                    <span className="text-[12px] font-bold leading-normal text-[#2D2D2D]">
                        Способ оплаты
                    </span>
                </div>
            </div>
            <div
                className="flex justify-between gap-[clamp(3px,0.811vw,5px)]"
                style={{ paddingInline: 'max(0px, calc(clamp(28px, 7.568vw, 48px) - 5px))' }}
            >
                <CartChoiceOption
                    variant="payment"
                    active={paymentMethod === 'qr'}
                    onSelect={() => setPaymentMethod('qr')}
                    label="Оплата по QR-коду"
                    primary="СБП"
                    secondary="без комиссии"
                />
                <CartChoiceOption
                    variant="payment"
                    active={paymentMethod === 'card'}
                    onSelect={() => setPaymentMethod('card')}
                    label="Банковская карта"
                    primary="Онлайн"
                    secondary="МИР, Visa"
                />
            </div>
        </div>
        <div style={{ paddingInline: 'max(0px, calc(clamp(28px, 7.568vw, 48px) - 5px))' }}>
            <div className="flex justify-between font-manrope text-[12px] font-bold leading-normal text-[#2D2D2D]">
                <span>Итого</span>
                <span>{formatCartPrice(grandTotal)}</span>
            </div>
            <div className="mt-[clamp(18px,4.865vw,31px)] flex flex-col gap-[clamp(5px,1.351vw,9px)] font-manrope text-[10px] font-normal leading-normal text-[#666666]">
                {renderAgreementCheckbox({
                    id: `${agreementIdPrefix}-offer-checkbox`,
                    checked: isOfferAccepted,
                    onToggle: setIsOfferAccepted,
                    children: (
                        <>
                            Я соглашаюсь с{' '}
                            <a href="/offer" className="underline hover:opacity-70" target="_blank">
                                условиями публичной оферты
                            </a>
                        </>
                    ),
                })}
                {renderAgreementCheckbox({
                    id: `${agreementIdPrefix}-policy-checkbox`,
                    checked: isPolicyAccepted,
                    onToggle: setIsPolicyAccepted,
                    children: (
                        <>
                            Я принимаю{' '}
                            <a href="/policy" className="underline hover:opacity-70" target="_blank">
                                политику конфиденциальности
                            </a>
                        </>
                    ),
                })}
            </div>
        </div>
    </section>
);
