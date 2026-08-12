"use client";

import React from 'react';
import { Container } from '@/components/shared/Container';
import { Text } from '@/components/shared/Text';
import { Button } from '@/components/shared/Button';
import NextLink from 'next/link';

export default function OrderErrorPage() {
    return (
        <Container size="1200" className="flex flex-col items-center justify-center min-h-[60vh] text-center pt-[130px] mb-[100px]">
            <Text size={20} className="mb-4 text-black">Заказ не был оформлен</Text>

            <div className="flex flex-col gap-1 mb-10 text-[11px] text-black">
                <p>Что-то пошло не так.</p>
                <p>Попробуйте снова.</p>
            </div>

            <div className="mb-10 text-[#666666]">
                <svg width="30" height="30" viewBox="0 0 30 30" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M2.5 2.5L27.5 27.5M27.5 2.5L2.5 27.5" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
            </div>

            <NextLink href="/checkout">
                <Button variant="secondary" className="w-[300px] h-[45px] bg-[linear-gradient(180deg,#FFFFFF_0%,#F2F2F2_100%)] border border-black/5 hover:opacity-80 rounded-[8px] shadow-sm">
                    <Text size={16} className="text-black">вернуться в корзину</Text>
                </Button>
            </NextLink>
        </Container>
    );
}
