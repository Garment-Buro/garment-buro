import type { HardwareCategory } from '@/lib/constructor/types';

export const CONSTRUCTOR_CATEGORIES: Array<{ id: HardwareCategory; name: string }> = [
    { id: 'prints', name: 'Принты' },
    { id: 'rivets', name: 'Заклепки' },
    { id: 'distress', name: 'Дистресс' },
    { id: 'zippers', name: 'Молнии' },
    { id: 'pullers', name: 'Пуллеры' },
    { id: 'embroidery', name: 'Вышивка' },
];
