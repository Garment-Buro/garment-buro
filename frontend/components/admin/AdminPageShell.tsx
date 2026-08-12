'use client';

import type { ReactNode } from 'react';
import NextLink from 'next/link';

import { Container } from '@/components/shared/Container';
import { Text } from '@/components/shared/Text';
import { useIdentityAccess } from '@/hooks/auth/useIdentityAccess';

export type AdminSection = 'products' | 'orders' | 'crm';

type AdminPageShellProps = {
    activeSection: AdminSection;
    title: string;
    action?: ReactNode;
    children: ReactNode;
};

const SECTIONS: Array<{ href: string; label: string; value: AdminSection }> = [
    { href: '/admin', label: 'Товары', value: 'products' },
    { href: '/admin/orders', label: 'Заказы', value: 'orders' },
    { href: '/admin/crm', label: 'Производство', value: 'crm' },
];

const getNavigationClassName = (isActive: boolean) => isActive
    ? 'px-4 py-2 bg-black text-white rounded-md cursor-pointer'
    : 'px-4 py-2 bg-gray-200 text-black rounded-md cursor-pointer hover:bg-gray-300';

export function AdminPageShell({ activeSection, title, action, children }: AdminPageShellProps) {
    const { enabled: crmEnabled, hasCrmAccess } = useIdentityAccess();
    const visibleSections = SECTIONS.filter(section => (
        section.value !== 'crm' || (crmEnabled && hasCrmAccess)
    ));

    return (
        <Container className="pt-32 pb-20 min-h-screen">
            <nav className="mb-8 flex flex-wrap gap-4" aria-label="Разделы администрирования">
                {visibleSections.map((section) => (
                    <NextLink
                        key={section.value}
                        href={section.href}
                        className={getNavigationClassName(section.value === activeSection)}
                        aria-current={section.value === activeSection ? 'page' : undefined}
                    >
                        {section.label}
                    </NextLink>
                ))}
            </nav>

            <div className="flex justify-between items-center mb-10 text-black">
                <Text size={24} weight="semibold">{title}</Text>
                {action}
            </div>

            {children}
        </Container>
    );
}
