import NextLink, { type LinkProps as NextLinkProps } from 'next/link';
import type { AnchorHTMLAttributes, CSSProperties, ReactNode } from 'react';

type LinkProps = NextLinkProps
    & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, keyof NextLinkProps>
    & {
        children: ReactNode;
        size?: number | string;
    };

export const Link = ({
    children,
    className = '',
    size,
    style,
    ...props
}: LinkProps) => {
    const hasTextColor = className.includes('text-');
    const colorClass = hasTextColor ? '' : 'text-black';
    const fontStyle: CSSProperties | undefined = size
        ? {
            fontSize: typeof size === 'number' ? `${size}px` : size,
            ...style,
        }
        : style;

    return (
        <NextLink
            {...props}
            className={`cursor-pointer font-manrope no-underline transition-opacity hover:opacity-80 focus-visible:opacity-80 ${colorClass} ${className}`}
            style={fontStyle}
        >
            {children}
        </NextLink>
    );
};
