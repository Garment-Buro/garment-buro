import type { ReactNode } from 'react';

import { Text } from '@/components/shared/Text';

type ProductFormSectionProps = {
    title: string;
    children: ReactNode;
    tone?: 'default' | 'desktop' | 'mobile';
    gap?: 'compact' | 'normal';
};

const TONE_CLASSES = {
    default: '',
    desktop: 'p-6 border rounded-md bg-gray-50',
    mobile: 'p-6 border rounded-md bg-gray-50',
};

const TITLE_CLASSES = {
    default: 'border-b pb-2',
    desktop: 'text-blue-600',
    mobile: 'text-purple-600',
};

export function ProductFormSection({ title, children, tone = 'default', gap = 'normal' }: ProductFormSectionProps) {
    return (
        <section className={`flex flex-col ${gap === 'compact' ? 'gap-4' : 'gap-6'} ${TONE_CLASSES[tone]}`}>
            <Text size={18} weight="semibold" className={TITLE_CLASSES[tone]}>{title}</Text>
            {children}
        </section>
    );
}
