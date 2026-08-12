import Image from 'next/image';

import type { CartItem } from '@/lib/cart/types';
import { CART_ACTION_PRODUCT_SECTION_BACKGROUND } from '@/lib/cart/constants';
import { formatCartPrice } from '@/lib/cart/utils/cartAction';

import { CartQuantityControl } from './CartQuantityControl';

type CartAddProductCardProps = {
    title: string;
    color: string;
    price: number;
    image: string;
    item?: CartItem;
    disabled: boolean;
    onAdd: () => void;
    onEdit: () => void;
    onDetails: (item: CartItem) => void;
    updateQuantity: (id: string, quantity: number) => void;
};

export const CartAddProductCard = ({
    title,
    color,
    price,
    image,
    item,
    disabled,
    onAdd,
    onEdit,
    onDetails,
    updateQuantity,
}: CartAddProductCardProps) => (
    <div
        className="cart-action-bar-add-product-card grid w-full grid-cols-[clamp(96px,25.946vw,166px)_minmax(0,1fr)_clamp(124px,33.514vw,214px)] gap-x-[clamp(12px,3.243vw,21px)] px-[clamp(22px,5.946vw,38px)] py-[clamp(16px,4.324vw,28px)]"
        style={{ background: CART_ACTION_PRODUCT_SECTION_BACKGROUND }}
    >
        <div className="row-span-4 flex h-[clamp(169px,45.676vw,292px)] w-[clamp(95px,25.676vw,164px)] items-center justify-center overflow-hidden">
            <Image src={image} alt="" width={95} height={169} className="h-full w-full object-contain object-center" />
        </div>
        <div className="cart-action-bar-add-product-title-row col-span-2 flex min-w-0 items-start justify-between gap-[8px]">
            <div className="min-w-0 pr-[10px] font-manrope text-[12px] font-medium leading-[1.18] text-[#2D2D2D]">{title}</div>
            <button
                type="button"
                onClick={onEdit}
                aria-label="Изменить товар в конструкторе"
                className="flex shrink-0 items-center justify-center"
                style={{ padding: '6px', borderRadius: 5, border: '1px solid #E5E5E5', background: 'rgba(255, 255, 255, 0.6)', boxShadow: '0 1px 1.8px 0 rgba(0, 0, 0, 0.26)' }}
            >
                <Image src="/edit_icon.svg" alt="" width={18} height={18} aria-hidden="true" className="h-[18px] w-[18px]" />
            </button>
        </div>
        <div className="col-span-2 mt-[8px] font-manrope text-[10px] font-medium leading-[1.3] text-[#666666]">
            <div>Цвет: {color || '—'}</div><div>Размер: —</div>
        </div>
        <button
            type="button"
            className="col-span-2 mt-[18px] flex items-center gap-[4px] justify-self-start font-manrope text-[10px] font-medium leading-none text-[#636363]"
            onClick={() => item && onDetails(item)}
        >
            <span>Подробнее</span><span aria-hidden="true">&gt;</span>
        </button>
        <div className="col-start-2 self-end font-manrope text-[12px] font-medium leading-normal text-[#2D2D2D]">{formatCartPrice(price)}</div>
        {item ? (
            <CartQuantityControl item={item} updateQuantity={updateQuantity} variant="product-card" />
        ) : (
            <button
                type="button"
                onClick={onAdd}
                disabled={disabled}
                className="col-start-3 row-start-4 flex h-[clamp(34px,9.189vw,59px)] w-[clamp(124px,33.514vw,214px)] self-end items-center justify-center rounded-[5px] border border-[#E5E5E5] bg-[rgba(255,255,255,0.6)] font-manrope text-[36px] font-medium leading-none text-[#989898] disabled:opacity-45"
                style={{ boxShadow: '0 1px 1.8px 0 rgba(0, 0, 0, 0.26)' }}
                aria-label="Добавить товар в корзину"
            >
                <span>+</span>
            </button>
        )}
    </div>
);

