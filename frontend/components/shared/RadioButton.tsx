import React from 'react';

interface RadioButtonProps extends React.InputHTMLAttributes<HTMLInputElement> {
    label?: React.ReactNode;
}

export const RadioButton: React.FC<RadioButtonProps> = ({
    label,
    id,
    className = '',
    ...props
}) => {
    const generatedId = React.useId();
    const radioId = id || `radio-${generatedId}`;

    return (
        <div className={`flex items-center gap-[12px] ${className}`}>
            <div className="relative flex items-center justify-center">
                <input
                    type="radio"
                    id={radioId}
                    className="peer appearance-none w-[30px] h-[30px] rounded-full border-[1.936px] border-[#818181] outline-none cursor-pointer focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#818181]"
                    {...props}
                />
                {/* Inner circle for checked state */}
                <div className="absolute w-[18px] h-[18px] rounded-full bg-[#818181] scale-0 peer-checked:scale-100 transition-transform pointer-events-none" />
            </div>
            {label && (
                <label htmlFor={radioId} className="font-manrope text-[14px] cursor-pointer text-black">
                    {label}
                </label>
            )}
        </div>
    );
};
