"use client";

import { useRef, type ChangeEvent } from 'react';

import { RawMediaImage } from '@/components/shared/RawMediaImage';
import { useMediaUpload } from '@/hooks/media/useMediaUpload';
import { normalizeMediaUrl } from '@/lib/media/utils/mediaUrl';
import { IMAGE_FILE_ACCEPT } from '@/lib/media/utils/upload';

type VariantImageSlotProps = {
    url: string;
    label: string;
    onUpload: (url: string) => void;
    onRemove?: () => void;
};

export const VariantImageSlot = ({
    url,
    label,
    onUpload,
    onRemove,
}: VariantImageSlotProps) => {
    const inputRef = useRef<HTMLInputElement>(null);
    const { isUploading, upload } = useMediaUpload();
    const resolvedUrl = normalizeMediaUrl(url);

    const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;
        const uploadedUrl = await upload(file);
        if (uploadedUrl) onUpload(uploadedUrl);
        else alert('Ошибка загрузки');
    };

    return (
        <div
            onClick={() => !url && inputRef.current?.click()}
            className={`relative group rounded-[10px] overflow-hidden border-2 border-dashed transition-all
                ${resolvedUrl ? 'border-transparent' : 'border-black/20 hover:border-black/50 cursor-pointer'}
                w-full aspect-3/4 bg-[#F3F3F3] flex items-center justify-center`}
        >
            {isUploading && (
                <div className="absolute inset-0 bg-black/40 flex items-center justify-center z-10">
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                </div>
            )}
            {resolvedUrl ? (
                <>
                    <RawMediaImage
                        src={resolvedUrl}
                        className="w-full h-full object-cover"
                        alt=""
                        onError={(event) => {
                            const target = event.currentTarget;
                            if (target.src.endsWith('/landing-bg.webp')) return;
                            target.src = '/landing-bg.webp';
                        }}
                    />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100">
                        <button
                            type="button"
                            onClick={event => {
                                event.stopPropagation();
                                inputRef.current?.click();
                            }}
                            className="w-8 h-8 rounded-full bg-white/90 flex items-center justify-center text-black text-[14px] hover:bg-white"
                        >
                            ↑
                        </button>
                        {onRemove && (
                            <button
                                type="button"
                                onClick={event => {
                                    event.stopPropagation();
                                    onRemove();
                                }}
                                className="w-8 h-8 rounded-full bg-red-500/90 flex items-center justify-center text-white text-[12px] hover:bg-red-500"
                            >
                                ✕
                            </button>
                        )}
                    </div>
                </>
            ) : (
                <div className="flex flex-col items-center gap-1 text-black/30 pointer-events-none select-none">
                    <span className="text-[22px]">+</span>
                    <span className="text-[9px] text-center px-2">{label}</span>
                </div>
            )}
            <input ref={inputRef} type="file" accept={IMAGE_FILE_ACCEPT} className="hidden" onChange={handleFile} />
        </div>
    );
};
