"use client";

import React from 'react';
import { PlatformEntry } from '@/components/platform/PlatformEntry';
import { Popup } from '@/components/shared/Popup';
import { OrderContent } from '@/components/shared/OrderContent';
import { useRouter } from 'next/navigation';

export default function OrderStatusPage() {
    const router = useRouter();

    return (
        <>
            <PlatformEntry />

            {/* Order popup overlaid on top */}
            <Popup maxWidth={560} onClose={() => router.push('/')}>
                <OrderContent />
            </Popup>
        </>
    );
}
