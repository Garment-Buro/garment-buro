'use client';

import { useState } from 'react';
import { AppIcon } from '@/components/icons/AppIcon';
import type { CartDeliveryMethod } from '@/lib/cart/actionTypes';
import { CART_ACTION_PRODUCT_SECTION_BACKGROUND } from '@/lib/cart/constants';
import { formatCourierAddress, validCourierAddress } from '@/lib/checkout/contact';
import { getOfficeAddress } from '@/lib/cdek/utils/cdek';
import { useCheckoutDetailsStore } from '@/store/checkoutDetailsStore';
import { DeliverySheet } from './DeliverySheet';
import { RecipientSheet } from './RecipientSheet';
import styles from './CheckoutSheet.module.css';

export function CartDeliveryDetails({ method, onChange }: { method: CartDeliveryMethod; onChange: (method: CartDeliveryMethod) => void }) {
    const details = useCheckoutDetailsStore();
    const [sheet, setSheet] = useState<'delivery' | 'recipient' | null>(null);
    const address = method === 'pickup'
        ? details.point ? `${details.point.location?.city}, ${getOfficeAddress(details.point)}` : 'Выберите пункт на карте или в списке'
        : validCourierAddress(details.courier) ? formatCourierAddress(details.courier) : 'Укажите адрес курьера';
    const recipient = details.recipientIsBuyer ? details.buyer : details.recipient;
    return <>
        <button type="button" className={styles.summaryButton} style={{ background: CART_ACTION_PRODUCT_SECTION_BACKGROUND }} onClick={() => setSheet('delivery')}>
            <span><strong><AppIcon name="map-pin" width={14} height={16} />{method === 'pickup' ? 'Пункт выдачи СДЭК' : 'Доставка курьером'}</strong><small>{address}</small></span><span aria-hidden="true">›</span>
        </button>
        <div className="h-2" aria-hidden="true" />
        <button type="button" className={styles.summaryButton} style={{ background: CART_ACTION_PRODUCT_SECTION_BACKGROUND }} onClick={() => setSheet('recipient')}>
            <span><strong><AppIcon name="customer" width={14} height={16} />Получатель</strong><small>{recipient.name ? `${recipient.name}, ${recipient.phone}` : 'Заполните ваши данные и данные получателя'}</small></span><span aria-hidden="true">›</span>
        </button>
        {sheet === 'delivery' && <DeliverySheet method={method} onSave={onChange} onClose={() => setSheet(null)} />}
        {sheet === 'recipient' && <RecipientSheet onClose={() => setSheet(null)} />}
    </>;
}
