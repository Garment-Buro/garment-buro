import Image from 'next/image';
import React from 'react';

import type { CartItem } from '@/lib/cart/types';
import { getCartItemDetailsImage, getCartItemDetailsRows } from '@/lib/cart/utils/cartAction';

type CartItemDetailsPopupProps = {
    item: CartItem;
    onClose: () => void;
    onEdit: () => void;
};

export const CartItemDetailsPopup = ({ item, onClose, onEdit }: CartItemDetailsPopupProps) => {
    const detailsRows = getCartItemDetailsRows(item);
    return (
        <div className="cart-action-bar-details-popup fixed inset-0 z-[140] flex items-center justify-center bg-black/40 px-[8px]" onClick={onClose}>
            <div
                className="relative h-[min(416px,calc(100dvh-32px))] w-[min(355px,calc(100vw-16px))] overflow-hidden rounded-[20px] border border-white/70 p-[5px]"
                style={{ background: 'linear-gradient(180deg, rgba(246,246,246,0.62) 0%, #E0E0E0 100%)' }}
                onClick={event => event.stopPropagation()}
            >
                <div className="relative h-[406px] max-h-full overflow-hidden rounded-[15px] border border-[#D9D9D9] bg-[#F3F3F3]" style={{ boxShadow: '0 2px 5px 0 rgba(0, 0, 0, 0.25) inset' }}>
                    <button type="button" onClick={onClose} className="absolute right-[20px] top-[18px] z-20 flex h-[20px] w-[20px] items-center justify-center" aria-label="Закрыть детали товара">
                        <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" fill="none">
                            <path d="M1 1L13 13M13 1L1 13" stroke="#9A9A9A" strokeWidth="1" strokeLinecap="round" />
                        </svg>
                    </button>
                    <div className="grid h-full grid-cols-[205px_minmax(0,1fr)] gap-[0px] px-[8px] pb-[8px] pt-[53px]">
                        <div className="cart-action-bar-details-images flex h-full flex-col items-center gap-[0px] overflow-hidden">
                            {(['front', 'back'] as const).map(view => (
                                <div key={view} className="cart-action-bar-details-image relative h-[170px] w-[205px] shrink-0">
                                    <Image src={getCartItemDetailsImage(item, view)} alt="" fill className="object-contain object-center" />
                                </div>
                            ))}
                        </div>
                        <div className="min-w-0 pl-[5px] pr-[5px] font-manrope text-black">
                            <button type="button" onClick={onEdit} className="mb-[14px] flex items-center gap-[8px] font-manrope text-[14px] font-semibold leading-[11.582px] text-[#BBBBBB]">
                                <Image src="/edit_icon.svg" alt="" width={12} height={12} aria-hidden="true" className="h-[12px] w-[12px] opacity-60" /><span>ИЗМЕНИТЬ</span>
                            </button>
                            <div className="whitespace-pre-line text-[12px] font-normal leading-normal">{item.title}</div>
                            <div className="mt-[12px] text-[10px] font-normal leading-normal"><div>Цвет: {item.color || '—'}</div><div>Размер: {item.size || '—'}</div></div>
                            <div className="mt-[16px] text-[8px] font-normal leading-normal">
                                <div className="text-[#999999]">Дополнительные детали:</div>
                                {detailsRows.length > 0 ? (
                                    <div className="mt-[2px] grid grid-cols-[minmax(0,1fr)_24px] gap-x-[5px]">
                                        {detailsRows.map(row => <React.Fragment key={row.name}><span className="min-w-0">{row.name}</span><span className="text-right">x{row.count}</span></React.Fragment>)}
                                    </div>
                                ) : <div className="mt-[2px] text-[#999999]">Нет дополнительных деталей</div>}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

