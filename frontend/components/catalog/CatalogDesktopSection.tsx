import Image from 'next/image';
import type { ReactNode } from 'react';

import { Container } from '@/components/shared/Container';

type CatalogDesktopSectionProps = {
    background: string;
    backgroundAlt: string;
    variant: 'hero' | 'center' | 'split';
    left: ReactNode;
    right?: ReactNode;
};

const SECTION_HEIGHTS = {
    hero: 'h-[720px]',
    center: 'h-[585px]',
    split: 'h-[585px]',
} as const;

export const CatalogDesktopSection = ({
    background,
    backgroundAlt,
    variant,
    left,
    right,
}: CatalogDesktopSectionProps) => (
    <section className={`relative w-full overflow-hidden ${SECTION_HEIGHTS[variant]}`}>
        <Image
            src={background}
            alt={backgroundAlt}
            fill
            priority={variant === 'hero'}
            className="object-cover"
        />
        <div className={`absolute inset-0 ${variant === 'hero' ? 'pt-[150px]' : ''}`}>
            <Container size="1200" className="h-full">
                <div className={variant === 'center'
                    ? 'flex h-full w-full items-center justify-center gap-[90px]'
                    : `flex h-full w-full justify-between gap-[90px] ${variant === 'hero' ? 'items-start pt-[50px]' : 'items-center'}`
                }>
                    <div className="flex gap-[90px]">{left}</div>
                    {right && <div className="flex gap-[90px]">{right}</div>}
                </div>
            </Container>
        </div>
    </section>
);
