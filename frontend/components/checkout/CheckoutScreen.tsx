'use client';

import { CheckoutFormColumn } from '@/components/checkout/CheckoutFormColumn';
import { CheckoutNavigation } from '@/components/checkout/CheckoutNavigation';
import { CheckoutOrderSummary } from '@/components/checkout/CheckoutOrderSummary';
import { Container } from '@/components/shared/Container';
import { useCheckout } from '@/hooks/checkout/useCheckout';

export function CheckoutScreen() {
    const controller = useCheckout();
    return (
        <form onSubmit={controller.submit} className="w-full">
            <Container size="1200" className="pt-[40px] pb-[100px] min-h-screen">
                <CheckoutNavigation variant="mobile" />
                <CheckoutNavigation variant="desktop" />
                <div className="flex flex-col-reverse lg:flex-row gap-[80px] lg:gap-[100px]">
                    <CheckoutFormColumn controller={controller} />
                    <CheckoutOrderSummary controller={controller} />
                </div>
            </Container>
        </form>
    );
}
