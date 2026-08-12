import React from 'react';
import { FaCheck } from 'react-icons/fa';

interface CheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> {
    label?: React.ReactNode;
}

export const Checkbox: React.FC<CheckboxProps> = ({
    label,
    id,
    className = '',
    ...props
}) => {
    const generatedId = React.useId();
    const checkboxId = id || `checkbox-${generatedId}`;

    return (
        <div className={`flex items-center gap-[12px] ${className}`}>
            <div className="relative flex items-center justify-center">
                <input
                    type="checkbox"
                    id={checkboxId}
                    className="peer appearance-none w-[30px] h-[30px] rounded-[8px] border border-[#818181] bg-transparent outline-none cursor-pointer focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#818181] transition-colors"
                    {...props}
                />
                {/* Checkmark icon, visible only when checked */}
                <div className="absolute text-[#818181] opacity-0 peer-checked:opacity-100 transition-opacity pointer-events-none">
                    <FaCheck size={16} />
                </div>
            </div>
            {label && (
                <label htmlFor={checkboxId} className="font-manrope text-[14px] cursor-pointer text-black">
                    {label}
                </label>
            )}
        </div>
    );
};
