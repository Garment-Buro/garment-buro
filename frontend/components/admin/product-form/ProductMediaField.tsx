import type { ChangeEvent } from 'react';

import { Text } from '@/components/shared/Text';
import { RawMediaImage } from '@/components/shared/RawMediaImage';
import { isVideoUrl, normalizeMediaUrl } from '@/lib/media/utils/mediaUrl';
import { IMAGE_FILE_ACCEPT } from '@/lib/media/utils/upload';

type ProductMediaFieldProps = {
    label: string;
    description?: string;
    value: string | string[];
    onChange: (event: ChangeEvent<HTMLInputElement>) => void;
    onRemove?: (index: number) => void;
    accept?: string;
    preview?: 'thumb' | 'contain' | 'video';
};

const FILE_INPUT_CLASS = 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-black file:text-white hover:file:bg-black/80';

function RemovablePreview({ url, onRemove }: { url: string; onRemove: () => void }) {
    return (
        <div className="relative group">
            <RawMediaImage
                src={normalizeMediaUrl(url)}
                className="w-20 h-20 object-cover rounded shadow-sm border border-black/10"
                alt=""
                onError={(event) => {
                    const target = event.currentTarget;
                    if (!target.src.endsWith('/landing-bg.webp')) target.src = '/landing-bg.webp';
                }}
            />
            <button type="button" onClick={onRemove} aria-label="Удалить изображение" className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity">✕</button>
        </div>
    );
}

export function ProductMediaField({ label, description, value, onChange, onRemove, accept = IMAGE_FILE_ACCEPT, preview = 'thumb' }: ProductMediaFieldProps) {
    const values = Array.isArray(value) ? value : value ? [value] : [];
    const multiple = Array.isArray(value);

    return (
        <div>
            <Text size={14} className="mb-2">{label}</Text>
            {description && <Text size={11} className="mb-2 text-gray-500">{description}</Text>}
            <input type="file" accept={accept} multiple={multiple} onChange={onChange} className={FILE_INPUT_CLASS} />
            {preview === 'video' && values[0] && (
                <div className="mt-2 flex flex-col gap-2">
                    {isVideoUrl(values[0]) && <video src={normalizeMediaUrl(values[0])} className="w-[240px] h-[135px] rounded border border-black/10 bg-black" controls preload="metadata" muted playsInline />}
                    <Text size={11} className="text-green-600 break-all">Загружено: {values[0]}</Text>
                </div>
            )}
            {preview !== 'video' && multiple && (
                <div className="flex flex-wrap gap-4 mt-4">
                    {values.map((url, index) => <RemovablePreview key={`${url}-${index}`} url={url} onRemove={() => onRemove?.(index)} />)}
                </div>
            )}
            {preview !== 'video' && !multiple && values[0] && (
                <RawMediaImage src={values[0]} alt="" className={preview === 'contain' ? 'w-40 h-auto object-contain mt-2 rounded border' : 'w-20 h-20 object-cover mt-2 rounded'} />
            )}
        </div>
    );
}
