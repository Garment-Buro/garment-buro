import Image from 'next/image';

import type { CartItem } from '@/lib/cart/types';
import { formatCartPrice } from '@/lib/cart/utils/cartAction';

import { CartQuantityControl } from './CartQuantityControl';

const ConstructedItemIcon = () => (
    <svg aria-hidden="true" width="13" height="13" viewBox="0 0 24 24" fill="none">
        <path d="M5 12.5l4.1 4.1L19 6.8" stroke="#32E36E" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

type CartItemRowProps = {
    item: CartItem;
    onEdit: () => void;
    onDetails: (item: CartItem) => void;
    updateQuantity: (id: string, quantity: number) => void;
};

export const CartItemRow = ({ item, onEdit, onDetails, updateQuantity }: CartItemRowProps) => (
    <div className="cart-action-bar-cart-item-row grid w-full grid-cols-[clamp(56px,15.135vw,97px)_minmax(0,1fr)_clamp(90px,24.324vw,156px)] gap-x-[clamp(23px,6.216vw,40px)] gap-y-[clamp(6px,1.622vw,10px)]">
        <div className="row-span-2 flex h-[clamp(59px,15.946vw,102px)] w-[clamp(56px,15.135vw,97px)] items-center justify-center overflow-hidden">
            <Image src={item.image || '/landing-bg.webp'} alt="" width={56} height={59} className="h-full w-full object-contain object-center" />
        </div>
        <div className="min-w-0">
            <div className="line-clamp-2 font-manrope text-[10px] font-medium leading-[1.22] text-[#2D2D2D]">{item.title}</div>
            <div className="mt-[8px] font-manrope text-[10px] font-medium leading-[1.25] text-[#666666]">
                <div>Цвет: {item.color || '—'}</div>
                <div>Размер: {item.size || '—'}</div>
            </div>
        </div>
        <div className="flex min-w-0 flex-col items-end">
            <div className="font-manrope text-[10px] font-medium leading-normal text-[#2D2D2D]">{formatCartPrice(item.price * item.quantity)}</div>
            <div
                className="mt-[clamp(10px,2.703vw,17px)] grid h-[clamp(18px,4.865vw,31px)] w-[clamp(90px,24.324vw,156px)] grid-cols-[1fr_1px_1fr] overflow-hidden rounded-[3px] border border-[#E5E5E5] bg-[rgba(255,255,255,0.6)]"
                style={{ boxShadow: '0 0.665px 1.196px 0 rgba(0, 0, 0, 0.26)' }}
            >
                <button type="button" onClick={onEdit} className="flex items-center justify-center" aria-label="Изменить товар">
                    <Image src="/edit_icon.svg" alt="" width={12} height={12} aria-hidden="true" className="h-[12px] w-[12px]" />
                </button>
                <span className="my-[3px] rounded-full bg-[#9A9A9A]" aria-hidden="true" />
                <span className="flex items-center justify-center">{item.customization?.kind === 'constructor' ? <ConstructedItemIcon /> : null}</span>
            </div>
        </div>
        <button
            type="button"
            className="col-span-2 col-start-1 ml-[6px] flex items-center gap-[4px] self-end justify-self-start font-manrope text-[10px] font-medium leading-none text-[#636363]"
            onClick={() => onDetails(item)}
        >
            <span>Подробнее</span><span aria-hidden="true">&gt;</span>
        </button>
        <CartQuantityControl item={item} updateQuantity={updateQuantity} variant="row" />
    </div>
);

