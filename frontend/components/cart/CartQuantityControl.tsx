import type { CartItem } from '@/lib/cart/types';

type CartQuantityControlProps = {
    item: CartItem;
    updateQuantity: (id: string, quantity: number) => void;
    variant: 'row' | 'product-card' | 'collapsed';
};

const VARIANT_STYLES = {
    row: {
        className: 'col-start-3 flex h-[clamp(18px,4.865vw,31px)] items-center justify-between font-manrope text-[14px] font-medium leading-normal text-[#4C4C4C]',
        decrementClassName: '',
        incrementClassName: '',
        style: undefined,
    },
    'product-card': {
        className: 'cart-action-bar-add-product-stepper col-start-3 row-start-4 grid h-[clamp(34px,9.189vw,59px)] w-[clamp(124px,33.514vw,214px)] self-end grid-cols-[clamp(37px,10vw,64px)_minmax(0,1fr)_clamp(37px,10vw,64px)] overflow-hidden rounded-[5px] border border-[#E5E5E5] bg-[rgba(255,255,255,0.6)] font-manrope text-[20px] font-medium leading-normal text-[#545454]',
        decrementClassName: 'flex h-full items-center justify-end',
        incrementClassName: 'flex h-full items-center justify-start',
        style: { boxShadow: '0 1px 1.8px 0 rgba(0, 0, 0, 0.26)' },
    },
    collapsed: {
        className: 'cart-action-bar-stepper grid h-[clamp(27px,7.297vw,47px)] w-[clamp(135px,36.486vw,234px)] shrink-0 grid-cols-[clamp(37px,10vw,64px)_minmax(0,1fr)_clamp(37px,10vw,64px)] overflow-hidden rounded-[5px] font-manrope text-[16px] font-medium leading-normal text-[#545454]',
        decrementClassName: 'flex h-full items-center justify-end',
        incrementClassName: 'flex h-full items-center justify-start',
        style: {
            background: 'rgba(255, 255, 255, 0.6)',
            border: '1px solid #E5E5E5',
            boxShadow: '0 1px 1.8px 0 rgba(0, 0, 0, 0.26)',
        },
    },
} as const;

export const CartQuantityControl = ({ item, updateQuantity, variant }: CartQuantityControlProps) => {
    const styles = VARIANT_STYLES[variant];
    return (
        <div className={styles.className} style={styles.style}>
            <button
                type="button"
                onClick={() => updateQuantity(item.id, item.quantity - 1)}
                className={styles.decrementClassName}
                aria-label="Уменьшить количество"
            >
                -
            </button>
            <span className={variant === 'row' ? undefined : 'flex h-full items-center justify-center text-center'}>
                {item.quantity}
            </span>
            <button
                type="button"
                onClick={() => updateQuantity(item.id, item.quantity + 1)}
                className={styles.incrementClassName}
                aria-label="Увеличить количество"
            >
                +
            </button>
        </div>
    );
};

