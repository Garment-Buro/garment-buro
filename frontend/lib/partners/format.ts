export const formatPartnerMoney = (value: string | number) => new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 2,
}).format(Number(value));

export const formatPartnerDate = (value: string) => new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
}).format(new Date(value));

export const formatPartnerPercent = (basisPoints: number) => (
    `${(basisPoints / 100).toLocaleString('ru-RU')}%`
);

export const calculatePendingPartnerBalance = ({
    earned,
    available,
    paid,
}: {
    earned: string;
    available: string;
    paid: string;
}) => Math.max(0, Number(earned) - Number(available) - Number(paid));
