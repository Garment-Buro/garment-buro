'use client';

import { memo } from 'react';

import type { CdekGoodsItem, CdekSelection } from '@/lib/checkout/types';
import { useCdekWidget } from '@/hooks/checkout/useCdekWidget';

type CdekMapProps = {
    cdekScriptLoaded: boolean;
    goods: CdekGoodsItem[];
    onChoose: (selection: CdekSelection) => void;
    onCalculate: (price: number) => void;
};

export const CdekMap = memo(function CdekMap({ cdekScriptLoaded, goods, onChoose, onCalculate }: CdekMapProps) {
    const { isReady } = useCdekWidget({ cdekScriptLoaded, goods, onChoose, onCalculate });

    return (
        <div className="relative w-full h-[500px] rounded-lg overflow-hidden border border-black/10 bg-[#FAFAFA]">
            {!isReady && (
                <div className="absolute inset-0 bg-[#FAFAFA] z-10 flex flex-col p-5 animate-pulse">
                    <div className="flex justify-between items-center mb-6"><div className="w-[40%] max-w-[200px] h-7 bg-[#E5E5E5] rounded-lg" /><div className="w-[30%] max-w-[120px] h-7 bg-[#E5E5E5] rounded-lg" /></div>
                    <div className="w-full h-[45px] bg-[#E5E5E5] rounded-xl mb-6" />
                    <div className="flex-1 w-full bg-[#E5E5E5]/60 rounded-xl" />
                </div>
            )}
            <div id="cdek-map" style={{ width: '100%', height: '100%', visibility: isReady ? 'visible' : 'hidden' }} />
        </div>
    );
});
