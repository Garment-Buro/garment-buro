import type { CartItem } from '@/lib/cart/types';

import type {
    CdekGoodsItem,
    CheckoutErrors,
    CheckoutFormValues,
    CheckoutOrderPayload,
} from '../types.ts';

export const EMPTY_CHECKOUT_FORM: CheckoutFormValues = {
    email: '', phone: '', firstName: '', lastName: '', patronymic: '',
    deliveryCity: '', deliveryAddress: '', deliveryMethod: '', cdekAddress: '', cdekPointCode: '',
    paymentMode: 'card', agreeOffer: false, agreePolicy: false,
};

export const formatRussianPhone = (value: string) => {
    const match = value.replace(/\D/g, '');
    if (!match) return '';
    let numbers = match;
    if (numbers.startsWith('7') || numbers.startsWith('8')) numbers = numbers.substring(1);

    let result = '+7';
    if (numbers.length > 0) result += ` (${numbers.substring(0, 3)}`;
    if (numbers.length > 3) result += `) ${numbers.substring(3, 6)}`;
    if (numbers.length > 6) result += `-${numbers.substring(6, 8)}`;
    if (numbers.length > 8) result += `-${numbers.substring(8, 10)}`;
    return result;
};

export const getCheckoutErrors = (form: CheckoutFormValues): CheckoutErrors => ({
    ...(!form.email ? { email: true } : {}),
    ...(!form.phone ? { phone: true } : {}),
    ...(!form.firstName ? { firstName: true } : {}),
    ...(!form.deliveryAddress ? { deliveryAddress: true } : {}),
    ...(!form.agreeOffer ? { agreeOffer: true } : {}),
    ...(!form.agreePolicy ? { agreePolicy: true } : {}),
});

export const createCdekGoods = (items: CartItem[]): CdekGoodsItem[] => {
    const goods = items.flatMap((item) => Array.from({ length: item.quantity }, () => ({
        width: 20, height: 10, length: 20, weight: 500,
    })));
    return goods.length ? goods : [{ width: 20, height: 10, length: 20, weight: 500 }];
};

export const getCartItemFitSummary = (item: CartItem) => {
    const fit = item.customization?.fit;
    if (!fit) return null;
    const sleeveLabel = fit.sleeveMode === 'height' ? 'под рост' : 'стандартные';
    return `Посадка: длина ${fit.lengthCm}, ширина ${fit.widthCm}, рукава ${sleeveLabel}`;
};

export const createCheckoutOrderPayload = ({
    form, items, totalPrice, deliveryPrice,
}: {
    form: CheckoutFormValues;
    items: CartItem[];
    totalPrice: number;
    deliveryPrice: number | null;
}): CheckoutOrderPayload => ({
    email: form.email,
    phone: form.phone,
    first_name: form.firstName,
    last_name: form.lastName,
    patronymic: form.patronymic,
    delivery_city: form.deliveryCity || 'Москва',
    delivery_method: form.deliveryMethod || 'cdek',
    delivery_address: form.deliveryAddress,
    payment_method: form.paymentMode,
    cart_items: JSON.stringify(items),
    total_price: totalPrice + (deliveryPrice || 0),
    delivery_price: deliveryPrice || 0,
    cdek_point_code: form.cdekPointCode || undefined,
});
