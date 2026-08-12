import React from 'react';

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
    label?: string;
    labelPosition?: 'top' | 'bottom';
    error?: string;
    helperText?: string;
}

export const Textarea: React.FC<TextareaProps> = ({
    label,
    labelPosition = 'top',
    error,
    helperText,
    className = '',
    id,
    disabled,
    ...props
}) => {
    const generatedId = React.useId();
    const textareaId = id || `textarea-${label?.toLowerCase().replace(/\s+/g, '-') || generatedId}`;

    const labelElement = label ? (
        <label htmlFor={textareaId} className="font-manrope text-[#000] text-[25px] block">
            {label}
        </label>
    ) : null;

    return (
        <div className={`flex flex-col gap-[12px] w-full ${className}`}>
            {labelPosition === 'top' && labelElement}

            <textarea
                id={textareaId}
                disabled={disabled}
                className={`
                    font-manrope text-[14px] text-[#000] font-normal w-full min-h-[120px]
                    rounded-[13.3px] px-[20px] py-[15px]
                    bg-[linear-gradient(180deg,#F3F3F3_-0.72%,#E7E7E7_100.37%)]
                    shadow-[inset_0_3.872px_7.744px_0_rgba(0,0,0,0.25)]
                    border border-transparent focus:border-[#000] outline-none
                    placeholder:text-[#828282] placeholder:font-manrope placeholder:text-[14px] placeholder:font-normal
                    disabled:opacity-50 disabled:cursor-not-allowed
                    transition-colors resize-y
                `}
                {...props}
            />

            {error && <p className="text-xs text-red-500 font-manrope">{error}</p>}
            {!error && helperText && <p className="text-xs text-gray-500 font-manrope">{helperText}</p>}

            {labelPosition === 'bottom' && labelElement}
        </div>
    );
};
