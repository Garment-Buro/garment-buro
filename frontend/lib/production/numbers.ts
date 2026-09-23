export const compactDecimal = (
    value: string | number | null | undefined,
): string => {
    const text = String(value ?? '').replace(',', '.');
    if (!text.includes('.')) return text;
    return text.replace(/0+$/, '').replace(/\.$/, '');
};
