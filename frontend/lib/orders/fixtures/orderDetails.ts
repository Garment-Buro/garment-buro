import type { OrderDetails } from '@/lib/orders/types';

export const createOrderDetailsFixture = (orderId: string): OrderDetails => ({
    id: orderId,
    status: 'processing',
    total_price: 5980,
    created_at: new Date().toISOString(),
    delivery_method: 'cdek_pickup',
    cart_items: JSON.stringify([{
        title: 'худи на молнии с мехом "Cold Оверсайз"',
        price: 5980,
        size: 'M',
        color: 'Черный',
        quantity: 1,
    }]),
});
