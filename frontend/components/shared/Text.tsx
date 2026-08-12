import React from 'react';

interface TextProps extends React.HTMLAttributes<HTMLParagraphElement | HTMLSpanElement> {
    children: React.ReactNode;
    as?: 'p' | 'span' | 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
    variant?: 'primary' | 'secondary';
    size?: number | string;
    weight?: 400 | 500 | 600 | 700 | 800 | 'normal' | 'medium' | 'semibold' | 'bold';
    strikethrough?: boolean;
    className?: string;
}

export const Text: React.FC<TextProps> = ({
    children,
    as: Component = 'p',
    variant = 'primary',
    size,
    weight = 'normal',
    strikethrough = false,
    className = '',
    style,
    ...props
}) => {
    const colorClass = variant === 'primary' ? 'text-black' : 'text-[#666666]';
    const decorationClass = strikethrough ? 'line-through' : '';

    // Handling font weight map
    const weightClassMap: Record<string | number, string> = {
        400: 'font-normal',
        'normal': 'font-normal',
        500: 'font-medium',
        'medium': 'font-medium',
        600: 'font-semibold',
        'semibold': 'font-semibold',
        700: 'font-bold',
        'bold': 'font-bold',
        800: 'font-extrabold',
    };

    const fontWeightClass = weightClassMap[weight] || 'font-normal';

    // Using inline style for precise pixel sizes to allow arbitrary values
    const fontStyle = size ? {
        fontSize: typeof size === 'number' ? `${size}px` : size,
        ...style
    } : style;

    return (
        <Component
            className={`font-manrope ${colorClass} ${fontWeightClass} ${decorationClass} ${className}`}
            style={fontStyle}
            {...props}
        >
            {children}
        </Component>
    );
};
