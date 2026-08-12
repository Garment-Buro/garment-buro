export const parseProductId = (value: string) => {
    const productId = Number(value);
    return Number.isInteger(productId) && productId > 0 ? productId : null;
};
