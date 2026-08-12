"use client";

import React from 'react';
import { LandingPage } from '@/components/shared/LandingPage';
import { Popup } from '@/components/shared/Popup';
import { OrderContent } from '@/components/shared/OrderContent';
import { useRouter } from 'next/navigation';

export default function OrderStatusPage() {
    const router = useRouter();

    return (
        <>
            {/* Landing page shows in the background */}
            <LandingPage />

            {/* Order popup overlaid on top */}
            <Popup maxWidth={560} onClose={() => router.push('/')}>
                <OrderContent />
            </Popup>
        </>
    );
}
