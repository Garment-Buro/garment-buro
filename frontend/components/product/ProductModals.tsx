"use client";

import Image from 'next/image';

import { Text } from '@/components/shared/Text';
import type { ProductPageViewModel } from '@/hooks/product/useProductPage';
import type { ProductData } from '@/lib/products/types';

type ProductSizeChartModalProps = {
    product: ProductData;
    isOpen: boolean;
    onClose: () => void;
};

export const ProductSizeChartModal = ({ product, isOpen, onClose }: ProductSizeChartModalProps) => {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-200 flex items-center justify-center lg:hidden">
            <div className="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity" onClick={onClose} />
            <div className="relative z-205 flex w-full max-w-[360px] animate-fade-in flex-col items-center rounded-[16px] bg-[#F5F5F5] p-4 pt-10 shadow-2xl">
                <button onClick={onClose} className="absolute top-4 right-4 text-gray-500 hover:text-black">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6L6 18M6 6L18 18" /></svg>
                </button>
                <div className="relative mt-2 flex aspect-square w-full flex-col items-center justify-center overflow-hidden rounded-md border border-black/5 bg-[#F5F5F5]">
                    <Image src={product.size_chart_img_1 || '/setka_1.svg'} alt="Size Diagram" fill className="object-contain" />
                </div>
                <div className="relative mt-4 flex aspect-2/1 w-full flex-col items-center justify-center overflow-hidden rounded-md border border-black/5 bg-[#F5F5F5]">
                    <Image src={product.size_chart_img_2 || '/setka_2.svg'} alt="Size Table" fill className="object-contain" />
                </div>
            </div>
        </div>
    );
};

export const ProductWaitlistModal = ({ page }: { page: ProductPageViewModel }) => {
    const {
        showWaitlistForm,
        setShowWaitlistForm,
        waitlistSent,
        waitlistData,
        updateWaitlistField,
        handleWaitlistSubmit,
    } = page;

    if (!showWaitlistForm) return null;

    return (
        <div className="fixed inset-0 z-200 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity" onClick={() => setShowWaitlistForm(false)} />
            <div className="relative z-205 flex w-full max-w-[400px] animate-fade-in flex-col items-center rounded-[16px] bg-white p-8 shadow-2xl">
                <button onClick={() => setShowWaitlistForm(false)} className="absolute top-4 right-4 text-gray-400 hover:text-black">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6L6 18M6 6L18 18" /></svg>
                </button>

                {waitlistSent ? (
                    <div className="flex flex-col items-center justify-center py-10">
                        <Text size={18} weight="medium" className="mb-2 text-center text-black">Спасибо!</Text>
                        <Text size={14} className="text-center text-black/70">Мы сообщим вам, как только товар появится в наличии.</Text>
                    </div>
                ) : (
                    <form className="flex w-full flex-col gap-4 pt-2" onSubmit={handleWaitlistSubmit}>
                        <Text size={18} weight="semibold" className="mb-4 text-center leading-snug text-black">Узнать о поступлении</Text>
                        <input
                            className="h-[45px] w-full rounded-[6px] border border-black/20 px-4 font-manrope text-[14px] outline-none transition-colors focus:border-black"
                            type="text"
                            placeholder="Ваше Имя"
                            required
                            value={waitlistData.name}
                            onChange={event => updateWaitlistField('name', event.target.value)}
                        />
                        <input
                            className="h-[45px] w-full rounded-[6px] border border-black/20 px-4 font-manrope text-[14px] outline-none transition-colors focus:border-black"
                            type="email"
                            placeholder="Email"
                            required
                            value={waitlistData.email}
                            onChange={event => updateWaitlistField('email', event.target.value)}
                        />
                        <input
                            className="h-[45px] w-full rounded-[6px] border border-black/20 px-4 font-manrope text-[14px] outline-none transition-colors focus:border-black"
                            type="tel"
                            placeholder="Номер телефона"
                            required
                            value={waitlistData.phone}
                            onChange={event => updateWaitlistField('phone', event.target.value)}
                        />
                        <button type="submit" className="mt-2 flex h-[55px] w-full cursor-pointer items-center justify-center rounded-[12px] border border-white/80 bg-[linear-gradient(180deg,#FFFFFF_0%,#F0F0F0_100%)] font-manrope text-[14px] text-black shadow-[0_2px_10px_rgba(0,0,0,0.05)] transition-transform active:translate-y-px">
                            получить уведомление
                        </button>
                    </form>
                )}
            </div>
        </div>
    );
};
