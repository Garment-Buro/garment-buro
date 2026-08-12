import type { ProfileOrder } from '@/lib/unfinished/types';

export const PROFILE_FORM_FIXTURE = {
    loginEmail: 'ivanov_ivan@mail.ru',
    name: 'Иванов Иван',
    gender: 'Не выбран',
    phone: '+7 900 123 45 67',
    email: 'ivanov_ivan@gmail.com',
};

export const PROFILE_ORDER_FIXTURES: ProfileOrder[] = [
    { id: 'order-001', title: 'Заказ № 001', date: '29 окт. 2024', total: '5 980 ₽', paid: true },
    { id: 'order-002', title: 'Заказ № 001', date: '29 окт. 2024', total: '5 980 ₽', paid: true },
];

export const ORDER_STATUS_FIXTURES = [
    { label: 'Заказ подтверждён', date: '29 окт. 2024', done: true },
    { label: 'В пути', date: '29 окт. 2024', done: true },
    { label: 'Готов к выдаче', date: '29 окт. 2024', done: false },
    { label: 'Получен', date: '29 окт. 2024', done: false },
];

export const DISCOUNT_CARD_FIXTURES = [
    { value: '10%', title: 'Скидка на первый заказ', meta: 'активна', suffix: 'ещё 10 ч', note: 'Доступна при оформлении заказа', locked: false },
    { value: '10%', title: 'Уровень L', meta: '8 000 / 15 000 ₽', note: '', locked: true },
    { value: '5%', title: 'От 5 изделий', meta: '3 / 5 изделий', note: '', locked: true },
];
