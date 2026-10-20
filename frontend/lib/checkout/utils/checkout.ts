import type { CartItem } from '@/lib/cart/types';

import type {
    CheckoutOrderPayload,
    DeliveryCalculationResponse,
} from '../types.ts';
import type { CheckoutContact } from '../contact.ts';

export const getCartItemFitSummary = (item: CartItem) => {
    const fit = item.customization?.fit;
    if (!fit) return null;
    const sleeveLabel = fit.sleeveMode === 'height' ? 'под рост' : 'стандартные';
    return `Посадка: длина ${fit.lengthCm}, ширина ${fit.widthCm}, рукава ${sleeveLabel}`;
};

export const createCheckoutOrderPayload = ({
    buyer, recipient, items, quote, deliveryMethod, paymentMethod,
}: {
    buyer: CheckoutContact;
    recipient: CheckoutContact;
    items: CartItem[];
    quote: DeliveryCalculationResponse;
    deliveryMethod: 'cdek_pickup' | 'cdek_door';
    paymentMethod: 'card' | 'qr';
}): CheckoutOrderPayload => ({
    buyer: { ...buyer }, recipient: { ...recipient }, items,
    delivery_city: quote.delivery_city,
    delivery_method: deliveryMethod,
    delivery_address: quote.delivery_address,
    payment_method: paymentMethod,
    claimed_total_price: Math.round((items.reduce((sum, item) => sum + item.price * item.quantity, 0) + quote.delivery_price) * 100) / 100,
    delivery_price: quote.delivery_price,
    delivery_quote_token: quote.quote_token,
    cdek_point_code: quote.cdek_point_code || undefined,
    currency: 'RUB',
});
