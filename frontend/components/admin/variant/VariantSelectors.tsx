"use client";

import { useState } from 'react';

import type { ColorOption } from '@/lib/options/types';
import { useVariantOptionsStore } from '@/store/variantOptionsStore';

import { VariantOptionSelect } from './VariantOptionSelect';

type ColorSelectProps = {
    value: string;
    hex: string;
    onChange: (label: string, hex: string) => void;
};

export const ColorSelect = ({ value, hex, onChange }: ColorSelectProps) => {
    const [newLabel, setNewLabel] = useState('');
    const [newHex, setNewHex] = useState('#000000');
    const { colors, addColor } = useVariantOptionsStore();

    return (
        <VariantOptionSelect
            addLabel="Добавить свой цвет"
            trigger={(
                <>
                    <div className="w-4 h-4 rounded-full border border-black/20 shrink-0" style={{ backgroundColor: hex || '#eee' }} />
                    <span>{value || 'Выберите цвет'}</span>
                </>
            )}
            renderOptions={(close) => colors.map((color: ColorOption) => (
                <button
                    key={color.label}
                    type="button"
                    onClick={() => {
                        onChange(color.label, color.hex);
                        close();
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 text-[12px] font-manrope"
                >
                    <div className="w-4 h-4 rounded-full border border-black/20 shrink-0" style={{ backgroundColor: color.hex }} />
                    {color.label}
                </button>
            ))}
            renderEditor={({ close, cancelAdding }) => (
                <div className="p-3 border-t border-black/10 flex flex-col gap-2">
                    <input
                        type="text"
                        value={newLabel}
                        onChange={event => setNewLabel(event.target.value)}
                        placeholder="Название (напр. Хаки)"
                        className="w-full px-2 py-1 text-[12px] bg-[#F3F3F3] rounded outline-none"
                    />
                    <div className="flex items-center gap-2">
                        <input type="color" value={newHex} onChange={event => setNewHex(event.target.value)} className="w-8 h-8 rounded cursor-pointer border-0" />
                        <span className="text-[11px] text-gray-500">{newHex}</span>
                    </div>
                    <div className="flex gap-2">
                        <button
                            type="button"
                            onClick={async () => {
                                const label = newLabel.trim();
                                if (!label) return;
                                await addColor(label, newHex);
                                onChange(label, newHex);
                                setNewLabel('');
                                setNewHex('#000000');
                                close();
                            }}
                            className="flex-1 bg-black text-white text-[11px] py-1 rounded"
                        >
                            Добавить
                        </button>
                        <button type="button" onClick={cancelAdding} className="flex-1 bg-gray-100 text-[11px] py-1 rounded">Отмена</button>
                    </div>
                </div>
            )}
        />
    );
};

type SizeSelectProps = {
    value: string;
    onChange: (size: string) => void;
};

export const SizeSelect = ({ value, onChange }: SizeSelectProps) => {
    const [newSize, setNewSize] = useState('');
    const { sizes, addSize } = useVariantOptionsStore();

    const addCustomSize = async (close: () => void) => {
        const size = newSize.trim();
        if (!size) return;
        await addSize(size);
        onChange(size);
        setNewSize('');
        close();
    };

    return (
        <VariantOptionSelect
            addLabel="Добавить свой размер"
            trigger={<span className="font-medium">{value || 'Размер'}</span>}
            renderOptions={(close) => sizes.map(size => (
                <button
                    key={size}
                    type="button"
                    onClick={() => {
                        onChange(size);
                        close();
                    }}
                    className={`w-full px-3 py-2 text-[12px] font-manrope text-left hover:bg-gray-50 ${value === size ? 'font-semibold' : ''}`}
                >
                    {size}
                </button>
            ))}
            renderEditor={({ close, cancelAdding }) => (
                <div className="p-3 border-t border-black/10 flex flex-col gap-2">
                    <input
                        type="text"
                        value={newSize}
                        onChange={event => setNewSize(event.target.value)}
                        placeholder="Напр. 3XL или 42"
                        className="w-full px-2 py-1 text-[12px] bg-[#F3F3F3] rounded outline-none"
                        onKeyDown={event => {
                            if (event.key === 'Enter') void addCustomSize(close);
                        }}
                    />
                    <div className="flex gap-2">
                        <button type="button" onClick={() => void addCustomSize(close)} className="flex-1 bg-black text-white text-[11px] py-1 rounded">Добавить</button>
                        <button type="button" onClick={cancelAdding} className="flex-1 bg-gray-100 text-[11px] py-1 rounded">Отмена</button>
                    </div>
                </div>
            )}
        />
    );
};
