'use client';
import { CartChoiceOption } from './CartChoiceOption';

/** SBP cannot hold funds. Only offer it when the checkout policy explicitly permits it. */
export function CartSbpOption({
    active,
    onSelect,
    allowed,
}: {
    active: boolean;
    onSelect: () => void;
    allowed: boolean;
}) {
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
