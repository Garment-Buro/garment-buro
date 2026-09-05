"use client";

import type { CdekOffice, Coordinates } from '@/lib/cdek/types';
import { useCdekYandexMap } from '@/hooks/cdek/useCdekYandexMap';

type CdekYandexMapProps = {
    offices: CdekOffice[];
    selectedCode: string;
    searchCenter: Coordinates | null;
    selectedAddressLabel: string;
    onSelect: (code: string) => void;
};

export function CdekYandexMap({
    offices, selectedCode, searchCenter, selectedAddressLabel, onSelect,
}: CdekYandexMapProps) {
    const { mapNodeRef, mapState, officeCount } = useCdekYandexMap({
        offices,
        selectedCode,
        searchCenter,
        selectedAddressLabel,
        onSelect,
    });

    return (
        <div className="relative mb-4 h-[280px] overflow-hidden rounded-[24px] border border-black/10 bg-[#EDEDE8] md:h-[390px]">
            <div ref={mapNodeRef} className="absolute inset-0" />
            <div className="pointer-events-none absolute left-5 top-5 z-10 rounded-full bg-[#FCFCF8]/90 px-4 py-2 text-[12px] uppercase tracking-[0.16em] text-black/55 shadow-sm backdrop-blur">
                Пункты СДЭК: {officeCount}
            </div>
            {mapState === 'loading' && (
                <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#EDEDE8]">
                    <div className="rounded-2xl bg-[#FCFCF8] px-5 py-3 text-[13px] text-black/60 shadow-sm">Загружаю карту...</div>
                </div>
            )}
            {mapState === 'error' && (
                <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#EDEDE8] px-6 text-center">
                    <div className="max-w-[360px] rounded-3xl bg-[#FCFCF8] p-5 text-[13px] leading-relaxed text-black/65 shadow-sm">
                        Карту не удалось загрузить, но список ПВЗ ниже продолжает работать.
                    </div>
                </div>
            )}
        </div>
    );
}
