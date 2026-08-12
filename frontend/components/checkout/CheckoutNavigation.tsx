import NextLink from 'next/link';

type CheckoutNavigationProps = { variant: 'mobile' | 'desktop' };

export function CheckoutNavigation({ variant }: CheckoutNavigationProps) {
    const isMobile = variant === 'mobile';
    return (
        <div className={isMobile ? 'flex lg:hidden items-center relative mb-8 w-full justify-center' : 'hidden lg:block'}>
            <NextLink href="/" className={isMobile ? 'absolute left-0 text-[#A0A0A0] hover:text-black' : 'flex items-center text-gray-400 hover:text-black transition-colors mb-10 w-fit'} aria-label="Вернуться в каталог">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M19 12H5" stroke="currentColor" strokeWidth={isMobile ? '1.5' : '2'} strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M12 19L5 12L12 5" stroke="currentColor" strokeWidth={isMobile ? '1.5' : '2'} strokeLinecap="round" strokeLinejoin="round" />
                </svg>
            </NextLink>
        </div>
    );
}
