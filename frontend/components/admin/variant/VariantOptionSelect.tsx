"use client";

import { useState, type ReactNode } from 'react';

type VariantOptionSelectActions = {
    close: () => void;
    cancelAdding: () => void;
};

type VariantOptionSelectProps = {
    trigger: ReactNode;
    addLabel: string;
    renderOptions: (close: () => void) => ReactNode;
    renderEditor: (actions: VariantOptionSelectActions) => ReactNode;
};

export const VariantOptionSelect = ({
    trigger,
    addLabel,
    renderOptions,
    renderEditor,
}: VariantOptionSelectProps) => {
    const [isOpen, setIsOpen] = useState(false);
    const [isAdding, setIsAdding] = useState(false);
    const close = () => {
        setIsAdding(false);
        setIsOpen(false);
    };

    return (
        <div className="relative">
            <button
                type="button"
                onClick={() => setIsOpen(current => !current)}
                className="w-full flex items-center gap-2 px-3 py-2 bg-[#F3F3F3] rounded-[10px] text-[12px] font-manrope text-left"
            >
                {trigger}
                <svg className="ml-auto" width="8" height="5" viewBox="0 0 8 5">
                    <path d="M1 1L4 4L7 1" stroke="#666" strokeWidth="1.2" strokeLinecap="round" />
                </svg>
            </button>

            {isOpen && (
                <div className="absolute top-full left-0 mt-1 w-full bg-white border border-black/10 rounded-[10px] shadow-xl z-50 overflow-hidden">
                    <div className="max-h-[180px] overflow-y-auto">
                        {renderOptions(close)}
                    </div>
                    {isAdding ? (
                        renderEditor({ close, cancelAdding: () => setIsAdding(false) })
                    ) : (
                        <button
                            type="button"
                            onClick={() => setIsAdding(true)}
                            className="w-full px-3 py-2 text-[12px] text-blue-600 font-manrope border-t border-black/10 text-left hover:bg-blue-50"
                        >
                            + {addLabel}
                        </button>
                    )}
                </div>
            )}
        </div>
    );
};
