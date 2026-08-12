import React, { ReactNode } from 'react';

interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'prefix'> {
    label?: string;
    labelPosition?: 'top' | 'bottom';
    error?: string;
    helperText?: string;
    isLoading?: boolean;
    prefixNode?: ReactNode;
    suffixNode?: ReactNode;
}

export const Input: React.FC<InputProps> = ({
    label,
    labelPosition = 'top',
    error,
    helperText,
    isLoading,
    prefixNode,
    suffixNode,
    className = '',
    id,
    disabled,
    ...props
}) => {
    const generatedId = React.useId();
    const inputId = id || `input-${label?.toLowerCase().replace(/\s+/g, '-') || generatedId}`;

    const labelElement = label ? (
        <label htmlFor={inputId} className="font-manrope text-[#000] text-[25px] block">
            {label}
        </label>
    ) : null;

    return (
        <div className={`flex flex-col gap-[12px] w-full ${className}`}>
            {labelPosition === 'top' && labelElement}

            <div className="relative flex items-center w-full">
                {prefixNode && (
                    <div className="absolute left-[16px] z-10 text-gray-500">
                        {prefixNode}
                    </div>
                )}

                <input
                    id={inputId}
                    disabled={disabled || isLoading}
                    className={`
                        font-manrope text-[16px] text-[#000] font-normal w-full h-[52px]
                        rounded-[13.3px] px-[20px] 
                        ${prefixNode ? 'pl-[48px]' : ''} 
                        ${suffixNode || isLoading ? 'pr-[48px]' : ''}
                        bg-[linear-gradient(180deg,rgba(243,243,243,0.10)_-0.72%,rgba(231,231,231,0.10)_100.37%)]
                        shadow-[inset_0_1px_3px_0_rgba(0,0,0,0.25)]
                        border ${error ? 'border-red-500' : 'border-transparent focus:border-black/20'} outline-none
                        placeholder:text-[#828282] placeholder:font-manrope placeholder:text-[16px] placeholder:font-normal
                        disabled:opacity-50 disabled:cursor-not-allowed
                        transition-colors
                    `}
                    {...props}
                />

                {suffixNode && !isLoading && (
                    <div className="absolute right-[16px] z-10 text-gray-500">
                        {suffixNode}
                    </div>
                )}

                {isLoading && (
                    <div className="absolute right-[16px] z-10">
                        <svg className="animate-spin h-5 w-5 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                    </div>
                )}
            </div>

            {error && <p className="text-xs text-red-500 font-manrope">{error}</p>}
            {!error && helperText && <p className="text-xs text-gray-500 font-manrope">{helperText}</p>}

            {labelPosition === 'bottom' && labelElement}
        </div>
    );
};
