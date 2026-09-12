'use client';
import { useEffect, useState } from 'react';
import { requestJson } from '@/lib/api/http';
import { CartChoiceOption } from './CartChoiceOption';

/** SBP cannot hold funds. Only offer it when the checkout policy explicitly permits it. */
export function CartSbpOption({
    active,
    onSelect,
}: {
    active: boolean;
    onSelect: () => void;
}) {
    const [allowed, setAllowed] = useState(false);
    useEffect(() => {
        const controller = new AbortController();
        void requestJson<{ payment_methods: string[] }>(
            '/orders/checkout/options',
            { cache: 'no-store', signal: controller.signal },
        )
            .then((data) => setAllowed(data.payment_methods.includes('qr')))
            .catch(() => {});
        return () => controller.abort();
    }, []);
    return allowed ? (
        <CartChoiceOption
            variant="payment"
            active={active}
            onSelect={onSelect}
            label="Оплата по QR-коду"
            primary="СБП"
            secondary="без комиссии"
        />
    ) : null;
}
