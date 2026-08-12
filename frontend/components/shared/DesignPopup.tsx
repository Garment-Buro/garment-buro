"use client";

import React from 'react';
import { Popup } from './Popup';
import { Text } from './Text';

interface DesignPopupProps {
    isOpen: boolean;
    onClose: () => void;
}

export const DesignPopup: React.FC<DesignPopupProps> = ({ isOpen, onClose }) => {
    if (!isOpen) return null;

    return (
        <Popup onClose={onClose} maxWidth={500}>
            <div className="flex flex-col items-center text-center py-[75px] px-8">
                <Text size={16} className="text-black leading-relaxed font-manrope">
                    Кастомизировать вещь можно только в нашем приложении в Телеграмм
                </Text>
                
                <div className="mt-4">
                    <Text size={16} className="text-black font-manrope">
                        Войти <a href="https://t.me/plus2opacity" target="_blank" rel="noopener noreferrer" className="underline font-bold decoration-black underline-offset-4">здесь</a>
                    </Text>
                </div>
            </div>
        </Popup>
    );
};
