"use client";

import React from 'react';
import Image from 'next/image';
import styles from './CatalogQuantityControl.module.css';

interface CatalogQuantityControlProps {
    quantity: number;
    onAdd: () => void;
    onDecrease: () => void;
    onIncrease: () => void;
}

const surfaceClassName = 'shrink-0 rounded-[8px] bg-[linear-gradient(180deg,rgba(255,255,255,0.15)_0%,rgba(153,153,153,0.15)_100%)]';

export const CatalogQuantityControl: React.FC<CatalogQuantityControlProps> = ({
    quantity,
    onAdd,
    onDecrease,
    onIncrease,
}) => {
    const hasQuantity = quantity > 0;

    const runAction = (event: React.MouseEvent<HTMLButtonElement>, action: () => void) => {
        event.preventDefault();
        event.stopPropagation();
        action();
    };

    return (
        <div
            className={`catalog-quantity-control relative flex h-[34px] items-center overflow-hidden ${styles.control} ${hasQuantity ? 'shadow-[0_2px_0_rgba(0,0,0,0.11)]' : ''} ${surfaceClassName}`}
            style={{ width: hasQuantity ? 76 : 34 }}
            data-catalog-quantity-control={hasQuantity ? 'stepper' : 'add'}
        >
            {!hasQuantity ? (
                <button
                    type="button"
                    onClick={(event) => runAction(event, onAdd)}
                    className={`absolute inset-0 flex items-center justify-center ${styles.contentIn}`}
                    aria-label="Добавить в корзину"
                >
                    <Image src="/add_cart_catalog_plus.svg" alt="" width={14} height={17} className="h-[17px] w-[14px] object-contain" />
                </button>
            ) : (
                <div
                    className={`catalog-quantity-stepper absolute inset-0 flex items-center justify-between font-manrope text-black ${styles.contentIn}`}
                    role="group"
                    aria-label={`Количество в корзине: ${quantity}`}
                >
                    <button
                        type="button"
                        onClick={(event) => runAction(event, onDecrease)}
                        className="flex h-full min-w-[25px] flex-1 items-center justify-center text-[18px] font-normal leading-none"
                        aria-label="Уменьшить количество"
                    >
                        <span aria-hidden="true" className="-translate-y-px">−</span>
                    </button>
                    <span
                        className="catalog-quantity-value min-w-[16px] text-center text-[16px] font-normal leading-none tabular-nums"
                        aria-live="polite"
                    >
                        {quantity}
                    </span>
                    <button
                        type="button"
                        onClick={(event) => runAction(event, onIncrease)}
                        className="flex h-full min-w-[25px] flex-1 items-center justify-center text-[19px] font-normal leading-none"
                        aria-label="Увеличить количество"
                    >
                        <span aria-hidden="true" className="-translate-y-px">+</span>
                    </button>
                </div>
            )}
        </div>
    );
};
