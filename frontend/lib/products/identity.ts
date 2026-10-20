export function validateProductId(value: number): number {
    if (!Number.isInteger(value) || value <= 0 || value > 2_147_483_647) {
        throw new RangeError('A persisted product ID is required');
    }
    return value;
}

export function boundedProductIds(ids: readonly number[]): number[] {
    if (ids.length > 100) throw new RangeError('At most 100 product IDs per request');
    return [...new Set(ids.map(validateProductId))];
}

export const productConstructorHref = (productId: number) => (
    `/constructor?productId=${validateProductId(productId)}`
);
