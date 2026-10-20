import type { Dispatch, ReactNode, SetStateAction } from 'react';

import type { CartPaymentMethod } from '@/lib/cart/actionTypes';
import {
    CART_ACTION_PRODUCT_SECTION_BACKGROUND,
} from '@/lib/cart/constants';
import { formatCartPrice } from '@/lib/cart/utils/cartAction';

import { CartChoiceOption } from './CartChoiceOption';
import { CartSbpOption } from './CartSbpOption';

type CartTotalsSectionProps = {
    deliveryLabel?: string;
    productsTotal: number;
    deliveryPrice: number;
};

export const CartTotalsSection = ({
    deliveryLabel,
    productsTotal,
    deliveryPrice,
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
                <span>{deliveryLabel || (deliveryPrice > 0 ? formatCartPrice(deliveryPrice) : 'Бесплатно')}</span>
            </div>
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
    qrAvailable: boolean;
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
    qrAvailable,
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
                <CartSbpOption
                    allowed={qrAvailable}
                    active={paymentMethod === 'qr'}
                    onSelect={() => setPaymentMethod('qr')}
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
