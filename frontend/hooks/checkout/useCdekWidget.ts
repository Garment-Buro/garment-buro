"use client";

import { useEffect, useRef, useState } from 'react';
import type { CdekAddress, CdekGoodsItem, CdekSelection, CdekTariff } from '@/lib/checkout/types';
import { YANDEX_MAPS_API_KEY } from '@/lib/browser/config/vendorScripts';
import { runAfterInitialPaint } from '@/lib/browser/utils/scriptLoader';

declare global {
    interface Window {
        CDEKWidget: new (config: Record<string, unknown>) => { destroy: () => void };
        ymaps: unknown;
    }
}

type CdekWidgetOptions = {
    cdekScriptLoaded: boolean;
    goods: CdekGoodsItem[];
    onChoose: (selection: CdekSelection) => void;
    onCalculate: (price: number) => void;
};

export const useCdekWidget = ({ cdekScriptLoaded, goods, onChoose, onCalculate }: CdekWidgetOptions) => {
    const widgetRef = useRef<{ destroy: () => void } | null>(null);
    const [isReady, setIsReady] = useState(false);

    useEffect(() => {
        if (!cdekScriptLoaded) return;
        const element = document.getElementById('cdek-map');
        if (!element || !window.CDEKWidget) return;

        const cancelSchedule = runAfterInitialPaint(() => {
            if (widgetRef.current) {
                try { widgetRef.current.destroy(); } catch { /* already destroyed */ }
                widgetRef.current = null;
            }

            widgetRef.current = new window.CDEKWidget({
                from: { country_code: 'RU', city: 'Тверь', code: 245 },
                root: 'cdek-map',
                apiKey: YANDEX_MAPS_API_KEY,
                servicePath: '/service.php',
                defaultLocation: 'Москва',
                lang: 'rus', currency: 'RUB', canChoose: true, debug: false, goods,
                hideFilters: { have_cashless: false, have_cash: false, is_dressing_room: false, type: false },
                hideDeliveryOptions: { office: false, door: false },
                tariffs: { office: [234, 136, 138], door: [233, 137, 139] },
                onReady: () => setIsReady(true),
                onChoose: (deliveryType: string, tariff: CdekTariff, address: CdekAddress) => {
                    if (tariff?.delivery_sum !== undefined) onCalculate(Number(tariff.delivery_sum));
                    if (deliveryType === 'office') {
                        const city = address?.city || '';
                        onChoose({
                            address: [city, address?.name || '', address?.address || ''].filter(Boolean).join(', '),
                            city,
                            deliveryType,
                            cdekCode: address?.code,
                        });
                    } else {
                        onChoose({ address: address?.formatted || address?.address || '', city: address?.city || '', deliveryType });
                    }
                },
                onCalculate: (tariff: CdekTariff) => {
                    if (tariff?.delivery_sum !== undefined) onCalculate(Number(tariff.delivery_sum));
                },
            });
        });

        return () => {
            cancelSchedule();
            if (widgetRef.current) {
                try { widgetRef.current.destroy(); } catch (error) { console.warn('CDEK widget destroy error:', error); }
                widgetRef.current = null;
            }
        };
    }, [cdekScriptLoaded, goods, onCalculate, onChoose]);

    return { isReady };
};
