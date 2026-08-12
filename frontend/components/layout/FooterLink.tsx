"use client";

import { usePathname } from 'next/navigation';
import type { MouseEvent } from 'react';

import { DecryptedText } from '@/components/shared/DecryptedText';
import { Link } from '@/components/shared/Link';
import { useSettingsStore } from '@/store/settingsStore';

type FooterLinkProps = {
    settingKey: string;
    href: string;
    label: string;
    className?: string;
    size?: number | string;
};

export const FooterLink = ({
    settingKey,
    href,
    label,
    className,
    size,
}: FooterLinkProps) => {
    const pathname = usePathname();
    const settings = useSettingsStore(state => state.settings);
    const updateSettings = useSettingsStore(state => state.updateSettings);
    const configuredLink = settings?.links?.[settingKey];
    const displayLabel = configuredLink?.label || label;
    const displayHref = configuredLink?.url || href;
    const isEditing = pathname === '/admin/editor';

    const editLink = async (event: MouseEvent<HTMLAnchorElement | HTMLButtonElement>) => {
        if (!isEditing) return;
        event.preventDefault();
        event.stopPropagation();

        const nextLabel = window.prompt('Введите новый текст для этой ссылки:', displayLabel);
        if (nextLabel === null) return;
        const nextUrl = window.prompt('Введите новый URL для этой ссылки:', displayHref);
        if (nextUrl === null) return;

        await updateSettings({
            links: {
                ...(settings?.links || {}),
                [settingKey]: {
                    label: nextLabel.trim() || label,
                    url: nextUrl.trim() || href,
                },
            },
        });
    };

    return (
        <span className="group relative inline-flex">
            <Link
                href={displayHref}
                size={size}
                className={`${className || ''} ${isEditing ? 'cursor-pointer group-hover:opacity-50' : ''}`}
                onClick={editLink}
            >
                <DecryptedText text={displayLabel} />
            </Link>
            {isEditing ? (
                <button
                    type="button"
                    aria-label={`Редактировать ссылку «${displayLabel}»`}
                    onClick={editLink}
                    className="absolute -right-[10px] -top-[10px] z-50 hidden h-[24px] w-[24px] items-center justify-center rounded-full bg-black text-[10px] text-white shadow-lg group-hover:flex"
                >
                    ✎
                </button>
            ) : null}
        </span>
    );
};
