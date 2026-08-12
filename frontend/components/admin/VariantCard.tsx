"use client";

import { Text } from '../shared/Text';
import { Input } from '../shared/Input';
import type { ProductVariantData } from '@/lib/products/types';
import { ColorSelect, SizeSelect } from '@/components/admin/variant/VariantSelectors';
import { VariantImageSlot } from '@/components/admin/variant/VariantImageSlot';

export type VariantData = ProductVariantData;

interface VariantCardProps {
    variant: VariantData;
    index: number;
    onChange: (index: number, data: VariantData) => void;
    onRemove: (index: number) => void;
}

// ─── Main VariantCard ─────────────────────────────────────────────────────────
export function VariantCard({ variant, index, onChange, onRemove }: VariantCardProps) {
    const imageList = variant.images ? variant.images.split(',').filter(Boolean) : [];

    const update = (patch: Partial<VariantData>) => {
        onChange(index, { ...variant, ...patch });
    };

    const updateImages = (imgs: string[]) => {
        update({ images: imgs.join(',') });
    };

    return (
        <div className="relative group bg-white border border-black/10 rounded-[16px] p-4 flex flex-col gap-4 shadow-sm hover:shadow-md transition-shadow">
            {/* Remove button */}
            <button
                type="button"
                onClick={() => onRemove(index)}
                className="absolute top-3 right-3 w-6 h-6 rounded-full bg-red-50 text-red-500 hover:bg-red-500 hover:text-white flex items-center justify-center text-[12px] transition-colors opacity-0 group-hover:opacity-100"
            >
                ✕
            </button>

            {/* Header: Preview + Selects */}
            <div className="flex gap-3">
                {/* Preview Image */}
                <div className="w-[80px] shrink-0">
                    <Text size={9} className="mb-1 text-black/40 uppercase">Превью</Text>
                    <VariantImageSlot
                        url={variant.preview_image}
                        label="Фото вариации"
                        onUpload={url => update({ preview_image: url })}
                        onRemove={() => update({ preview_image: '' })}
                    />
                </div>

                {/* Selects + Stock */}
                <div className="flex-1 flex flex-col gap-2">
                    <div>
                        <Text size={9} className="mb-1 text-black/40 uppercase">Цвет</Text>
                        <ColorSelect
                            value={variant.color}
                            hex={variant.color_hex}
                            onChange={(label, hex) => update({ color: label, color_hex: hex })}
                        />
                    </div>
                    <div>
                        <Text size={9} className="mb-1 text-black/40 uppercase">Размер</Text>
                        <SizeSelect value={variant.size} onChange={s => update({ size: s })} />
                    </div>
                    <div>
                        <Text size={9} className="mb-1 text-black/40 uppercase">Количество</Text>
                        <Input
                            type="number"
                            value={variant.stock_quantity.toString()}
                            onChange={e => update({ stock_quantity: parseInt(e.target.value) || 0 })}
                            className="text-[12px]"
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <div>
                            <Text size={9} className="mb-1 text-black/40 uppercase">Ширина, см</Text>
                            <Input
                                type="number"
                                step="0.1"
                                value={variant.width_cm?.toString() || ''}
                                onChange={e => update({ width_cm: e.target.value ? parseFloat(e.target.value) : null })}
                                className="text-[12px]"
                            />
                        </div>
                        <div>
                            <Text size={9} className="mb-1 text-black/40 uppercase">Длина, см</Text>
                            <Input
                                type="number"
                                step="0.1"
                                value={variant.height_cm?.toString() || ''}
                                onChange={e => update({ height_cm: e.target.value ? parseFloat(e.target.value) : null })}
                                className="text-[12px]"
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* Additional photos */}
            <div>
                <Text size={9} className="mb-2 text-black/40 uppercase">Фото вариации</Text>
                <div className="grid grid-cols-4 gap-2">
                    {imageList.map((img, i) => (
                        <VariantImageSlot
                            key={i}
                            url={img}
                            label=""
                            onUpload={url => {
                                const next = [...imageList];
                                next[i] = url;
                                updateImages(next);
                            }}
                            onRemove={() => {
                                const next = imageList.filter((_, idx) => idx !== i);
                                updateImages(next);
                            }}
                        />
                    ))}
                    {/* Always show + slot if fewer than 8 */}
                    {imageList.length < 8 && (
                        <VariantImageSlot
                            url=""
                            label="+ фото"
                            onUpload={url => updateImages([...imageList, url])}
                        />
                    )}
                </div>
            </div>
        </div>
    );
}
