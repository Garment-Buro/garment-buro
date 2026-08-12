import Image from 'next/image';

import { DecryptedText } from '@/components/shared/DecryptedText';
import { Text } from '@/components/shared/Text';
import type { CheckoutController } from '@/hooks/checkout/useCheckout';
import { getCartItemFitSummary } from '@/lib/checkout/utils/checkout';

export function CheckoutOrderSummary({ controller }: { controller: CheckoutController }) {
    const { items, totalPrice, deliveryPrice, updateQuantity, removeItem } = controller;
    return (
        <div className="w-full lg:w-[450px] lg:sticky lg:top-[40px] lg:h-fit">
            <div className="mb-8 p-5 rounded-[13px] bg-[linear-gradient(180deg,rgba(243,243,243,0.10)_-0.72%,rgba(231,231,231,0.10)_100.37%)] shadow-[inset_0_1px_3px_0_rgba(0,0,0,0.25)]">
                <Text size={16} weight="semibold" className="mb-4 text-black">Итоговая сумма</Text>
                <div className="flex justify-between items-center py-2 border-b border-black/10"><Text size={13} className="text-black">Сумма товаров</Text><Text size={13} className="text-black"><DecryptedText text={`${totalPrice.toLocaleString('ru-RU')} ₽`} animateOn="none" /></Text></div>
                {deliveryPrice !== null && <div className="flex justify-between items-center py-2 border-b border-black/10"><Text size={13} className="text-black">Доставка СДЭК</Text><Text size={13} className="text-black"><DecryptedText text={`${deliveryPrice.toLocaleString('ru-RU')} ₽`} animateOn="none" /></Text></div>}
                <div className="flex justify-between items-center pt-3"><Text size={14} weight="semibold" className="text-black">Итого</Text><Text size={14} weight="semibold" className="text-black"><DecryptedText text={`${(totalPrice + (deliveryPrice || 0)).toLocaleString('ru-RU')} ₽`} animateOn="none" /></Text></div>
            </div>

            <Text size={16} weight="semibold" className="mb-4 text-black">Детали заказа</Text>
            <div className="flex flex-col">
                {items.length ? items.map((item) => {
                    const fitSummary = getCartItemFitSummary(item);
                    return (
                        <div key={item.id} className="flex items-start gap-4 py-8 relative border-t-0 border-b border-black/10">
                            <div className="w-[60px] h-[60px] lg:w-[80px] lg:h-[80px] bg-[#E5E5E5] rounded-md shrink-0 overflow-hidden"><Image src={item.image || '/landing-bg.webp'} alt={item.title} width={80} height={80} className="object-cover w-full h-full" /></div>
                            <div className="flex-1 flex flex-col min-h-[60px] lg:min-h-[80px]">
                                <Text size={13} weight="medium" className="text-black leading-tight max-w-[200px] mb-2 lg:font-normal lg:max-w-[220px]">{item.title}</Text>
                                <div className="flex w-full items-end justify-between mt-auto">
                                    <div className="flex flex-col">
                                        {item.color && <Text size={10} className="text-[#666666]">Цвет: {item.color}</Text>}
                                        {item.size && <Text size={10} className="text-[#666666]">Размер: {item.size}</Text>}
                                        {fitSummary && <Text size={10} className="max-w-[220px] text-[#666666]">{fitSummary}</Text>}
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <div className="flex items-center gap-3"><button type="button" onClick={() => updateQuantity(item.id, item.quantity - 1)} className="text-gray-400 hover:text-black">-</button><Text size={12} className="text-black">{item.quantity}</Text><button type="button" onClick={() => updateQuantity(item.id, item.quantity + 1)} className="text-gray-400 hover:text-black">+</button></div>
                                        <div className="flex items-center gap-3">
                                            <Text size={13} className="text-black lg:ml-2"><DecryptedText text={`${(item.price * item.quantity).toLocaleString('ru-RU')} ₽`} animateOn="none" /></Text>
                                            <button type="button" onClick={() => removeItem(item.id)} aria-label={`Удалить ${item.title}`} className="text-gray-400 hover:text-black flex items-center lg:absolute lg:right-0 lg:top-8"><svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M10.5 3.5L3.5 10.5M3.5 3.5L10.5 10.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" /></svg></button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                }) : <div className="py-10 text-center text-gray-400">Корзина пуста</div>}
            </div>
        </div>
    );
}
