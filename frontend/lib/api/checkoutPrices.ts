export type CheckoutItemPrice = { id: string; productId: number; price: number };

/** Keep only validated price fields from a definite pre-order rejection. */
export function readCheckoutPrices(detail: Record<string, unknown>, status: number): CheckoutItemPrice[] | null {
    if (status !== 409 || detail.code !== 'checkout_price_changed' || detail.currency !== 'RUB'
        || detail.order_id !== undefined || !Array.isArray(detail.prices)
        || !detail.prices.length || detail.prices.length > 100) return null;
    const prices: CheckoutItemPrice[] = [];
    for (const value of detail.prices) {
        if (!value || typeof value !== 'object') return null;
        const { id, product_id: productId, price } = value;
        if (typeof id !== 'string' || !id.trim() || id.length > 255
            || !Number.isSafeInteger(productId) || productId <= 0
            || typeof price !== 'number' || !Number.isFinite(price) || price < 0 || price > 9999999999.99
            || Math.abs(price * 100 - Math.round(price * 100)) > 0.0001
            || prices.some(item => item.id === id)) return null;
        prices.push({ id, productId, price });
    }
    return prices;
}
