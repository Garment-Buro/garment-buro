"use client";

import { CheckoutScreen } from '@/components/checkout/CheckoutScreen';
import { Text } from '@/components/shared/Text';
import { useClientReady } from '@/hooks/browser/useClientReady';

export default function CheckoutPage() {
    const mounted = useClientReady();

    if (!mounted) {
        return (
            <div className="w-full min-h-screen bg-[#F2F2F2] flex items-center justify-center">
                <title>Garment Buro | Оформление</title>
                <Text size={20}>Загрузка...</Text>
            </div>
        );
    }

    return (
        <>
            <title>Бюро Одежды | Оформление</title>
            <CheckoutScreen />
        </>
    );
}
