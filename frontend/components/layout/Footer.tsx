"use client";

import { usePathname } from 'next/navigation';

import { Text } from '@/components/shared/Text';
import { isSiteChromeHidden } from '@/lib/browser/utils/pageChrome';

import { FooterLink } from './FooterLink';

const PRIMARY_LINKS = [
    { href: '/delivery', label: 'ДОСТАВКА' },
    { href: '/policy', label: 'ПОЛИТИКА' },
    { href: '/payment', label: 'ОПЛАТА И ВОЗВРАТ' },
    { href: '/consent', label: 'СОГЛАСИЕ НА ОБРАБОТКУ ПЕРСОНАЛЬНЫХ ДАННЫХ' },
];

const SECONDARY_LINKS = [
    { href: '/offer', label: 'ОФЕРТА' },
    { href: '/consent-cookies', label: 'ИСПОЛЬЗОВАНИЕ COOKIE', mobileLabel: 'COOKIE' },
    { href: '/contacts', label: 'КОНТАКТЫ' },
    { href: '/presentation', label: 'ПРЕЗЕНТАЦИЯ' },
];

type FooterLinkItem = (typeof PRIMARY_LINKS)[number] | (typeof SECONDARY_LINKS)[number];

const FooterLinkList = ({
    links,
    mobile = false,
}: {
    links: FooterLinkItem[];
    mobile?: boolean;
}) => (
    <>
        {links.map((link) => (
            <FooterLink
                key={link.href}
                settingKey={link.label}
                href={link.href}
                label={mobile && 'mobileLabel' in link ? link.mobileLabel ?? link.label : link.label}
                size={mobile ? undefined : 10}
                className={mobile ? 'text-[10px] font-medium uppercase' : 'font-normal uppercase'}
            />
        ))}
    </>
);

export const Footer = () => {
    const pathname = usePathname();

    if (isSiteChromeHidden(pathname)) return null;

    return (
        <footer
            className="site-footer relative h-auto w-full overflow-hidden bg-cover bg-center font-manrope lg:h-[170px]"
            style={{ backgroundImage: 'url(/footer_bg.webp)' }}
        >
            <div className="hidden h-full w-full items-center justify-between px-[110px] lg:flex">
                <div className="flex flex-col uppercase leading-tight text-black">
                    <Text size={9} className="mb-1">ИП Клочинская Оксана Николаевна</Text>
                    <Text size={9}>ИНН: 690200757144</Text>
                    <Text size={9}>ОГРНИП: 325690000024450</Text>
                </div>

                <div className="flex self-stretch gap-[100px]">
                    <nav className="flex flex-col items-start justify-between gap-[13px] py-[45px]">
                        <FooterLinkList links={PRIMARY_LINKS} />
                    </nav>
                    <nav className="flex flex-col items-start justify-between gap-[13px] py-[45px]">
                        <FooterLinkList links={SECONDARY_LINKS} />
                    </nav>
                </div>
            </div>

            <div className="flex w-full flex-col px-8 py-12 font-manrope lg:hidden">
                <nav className="mb-16 flex flex-col gap-6">
                    <FooterLinkList links={PRIMARY_LINKS} mobile />
                </nav>

                <div className="flex items-end justify-between">
                    <div className="flex flex-col gap-0.5 text-[9px] uppercase leading-tight text-black">
                        <Text>ИП Клочинская Оксана Николаевна</Text>
                        <Text>ИНН: 690200757144</Text>
                        <Text>ОГРНИП: 325690000024450</Text>
                        <Text>info@garment-buro.ru</Text>
                    </div>

                    <nav className="flex flex-col items-start gap-6">
                        <FooterLinkList links={SECONDARY_LINKS} mobile />
                    </nav>
                </div>
            </div>
        </footer>
    );
};
