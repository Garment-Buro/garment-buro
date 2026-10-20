import NextLink from 'next/link';

import { CheckoutDeliverySection } from '@/components/checkout/CheckoutDeliverySection';
import { Checkbox } from '@/components/shared/Checkbox';
import { RadioButton } from '@/components/shared/RadioButton';
import { Text } from '@/components/shared/Text';
import type { CheckoutController } from '@/hooks/checkout/useCheckout';
import { PurchaseRecovery } from './PurchaseRecovery';
import { CartSyncNotice } from '@/components/cart/CartSyncNotice';

function CheckoutSubmitButton({ controller, variant }: { controller: CheckoutController; variant: 'desktop' | 'mobile' }) {
    const isDesktop = variant === 'desktop';
    return (
        <div className={`${isDesktop ? 'hidden lg:block' : 'block lg:hidden'} w-full mt-10`}>
            <div className={isDesktop ? '' : 'w-full flex justify-center'}>
                <button type="submit" disabled={controller.isSubmitting || controller.items.length === 0 || !controller.ready || !controller.quote || Boolean(controller.pending)} className="w-[85%] md:w-full h-[40px] md:h-[55px] rounded-[12px] shadow-[0_2px_10px_rgba(0,0,0,0.05)] bg-[linear-gradient(180deg,#FFFFFF_0%,#F0F0F0_100%)] border border-white/80 active:translate-y-px transition-transform flex items-center justify-center cursor-pointer disabled:opacity-50 text-black">
                    <Text size={isDesktop ? 18 : 14} className="tracking-wide text-black">
                        {controller.isSubmitting ? (isDesktop ? 'ОБРАБОТКА...' : 'Обработка...') : 'оформить заказ'}
                    </Text>
                </button>
            </div>
        </div>
    );
}

export function CheckoutFormColumn({ controller }: { controller: CheckoutController }) {
    const { form, setField, errors } = controller;
    return (
        <div className="flex-1 max-w-[500px] flex flex-col gap-8">
            <CartSyncNotice />
            <CheckoutDeliverySection controller={controller} />

            <div className="flex flex-col gap-4 mt-8 ml-1">
                <div>
                    <Checkbox checked={form.agreeOffer} onChange={event => setField('agreeOffer', event.target.checked)} label={<span className="font-manrope text-[14px] text-black">Я соглашаюсь с{' '}<NextLink href="/offer" className="underline hover:opacity-70" target="_blank">условиями публичной оферты</NextLink></span>} />
                    {errors.agreeOffer && <p className="text-xs text-red-500 font-manrope mt-1 ml-[42px]">Обязательное поле</p>}
                </div>
                <div>
                    <Checkbox checked={form.agreePolicy} onChange={event => setField('agreePolicy', event.target.checked)} label={<span className="font-manrope text-[14px] text-black">Я принимаю{' '}<NextLink href="/policy" className="underline hover:opacity-70" target="_blank">политику конфиденциальности</NextLink>{' '}и{' '}<NextLink href="/consent" className="underline hover:opacity-70" target="_blank">Согласие на обработку персональных данных</NextLink></span>} />
                    {errors.agreePolicy && <p className="text-xs text-red-500 font-manrope mt-1 ml-[42px]">Обязательное поле</p>}
                </div>
            </div>

            <div className="flex flex-col gap-6 mt-12">
                <Text size={20} className="mb-2 ml-1">Способ оплаты</Text>
                <div className="ml-1 flex flex-col gap-4">
                    <RadioButton checked={controller.effectivePaymentMethod === 'card'} onChange={() => setField('paymentMode', 'card')} label={<div className="flex flex-col justify-center ml-1"><Text size={15}>Банковская карта</Text></div>} />
                    {controller.qrAvailable && <RadioButton checked={controller.effectivePaymentMethod === 'qr'} onChange={() => setField('paymentMode', 'qr')} label={<div className="flex flex-col justify-center ml-1"><Text size={15}>QR-код</Text></div>} />}
                </div>
            </div>

            {controller.checkoutError && <p role="alert" className="text-sm text-red-800">{controller.checkoutError}</p>}
            <PurchaseRecovery pending={controller.pending} busy={controller.isSubmitting} onResume={controller.resumePurchase} onRetry={controller.retryPayment} onNew={controller.newPurchase} />
            <CheckoutSubmitButton controller={controller} variant="desktop" />
            <CheckoutSubmitButton controller={controller} variant="mobile" />
        </div>
    );
}
