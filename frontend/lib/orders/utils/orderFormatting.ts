const ORDER_STATUS_LABELS: Record<string, string> = {
    new: 'Новый',
    processing: 'В обработке',
    shipped: 'Отправлен',
    completed: 'Выполнен',
    cancelled: 'Отменен',
};

export const getOrderStatusLabel = (status: string) => ORDER_STATUS_LABELS[status] || status;

export const getOrderStatusClassName = (status: string) => {
    if (status === 'new') return 'bg-blue-100 text-blue-800';
    if (status === 'completed') return 'bg-green-100 text-green-800';
    return 'bg-gray-100 text-gray-800';
};

export const formatOrderDate = (value: string) => new Date(value).toLocaleString('ru-RU');

export const formatOrderPrice = (value: number) => `${value.toLocaleString('ru-RU')} ₽`;
