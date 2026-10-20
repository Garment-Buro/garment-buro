import { CartDeliveryDetails } from './CartDeliveryDetails';
import { Text } from '@/components/shared/Text';
import type { CheckoutController } from '@/hooks/checkout/useCheckout';

export function CheckoutDeliverySection({ controller }: { controller: CheckoutController }) {
    return <div className="flex flex-col gap-6 mt-8">
        <Text size={20} className="mb-2 ml-1">Доставка и получатель</Text>
        <CartDeliveryDetails method={controller.deliveryMethod} onChange={controller.setDeliveryMethod} />
        {!controller.quote && !controller.pending && <button type="button" disabled={controller.quoteLoading} onClick={controller.retryQuote} className="text-left text-sm underline disabled:opacity-50">
            {controller.quoteLoading ? 'Рассчитываем доставку…' : 'Рассчитать доставку'}
        </button>}
    </div>;
}
