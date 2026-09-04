import Link from 'next/link';

import { PartnerAttributionBootstrap } from '@/components/partner/PartnerAttributionBootstrap';
import type { PublicPartnerLanding as Landing } from '@/lib/partners/types';
import type { ProductData } from '@/lib/products/types';

type PublicPartnerLandingProps = {
    landing: Landing;
    products: ProductData[];
};

export const PublicPartnerLanding = ({ landing, products }: PublicPartnerLandingProps) => (
    <div className="min-h-dvh bg-[#f2f2ee] text-black">
        <PartnerAttributionBootstrap slug={landing.slug} />

        <header className="mx-auto flex max-w-[1200px] items-center justify-between px-6 py-6 lg:px-8">
            <Link href="/" className="text-xs font-semibold uppercase tracking-[0.18em]">GARMENT BURO</Link>
            <p className="text-xs text-black/45">Выбор {landing.partner_name}</p>
        </header>

        <main>
            <section className="mx-auto grid min-h-[70dvh] max-w-[1200px] items-center gap-10 px-6 pb-16 pt-8 lg:grid-cols-2 lg:px-8 lg:pb-24">
                <div className="max-w-xl">
                    {landing.eyebrow && (
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-black/45">
                            {landing.eyebrow}
                        </p>
                    )}
                    <h1 className="mt-5 text-4xl font-semibold leading-[1.04] tracking-[-0.045em] sm:text-5xl lg:text-7xl">
                        {landing.headline}
                    </h1>
                    <p className="mt-6 max-w-lg text-base leading-7 text-black/60 sm:text-lg">
                        {landing.description}
                    </p>
                    <Link
                        href={landing.cta_href}
                        className="mt-8 inline-flex h-12 items-center justify-center rounded-xl bg-black px-6 text-sm font-semibold text-white transition hover:bg-black/75"
                    >
                        {landing.cta_label}
                    </Link>
                </div>
                <div
                    className="aspect-[4/5] min-h-[420px] rounded-3xl bg-[#deded6] bg-cover bg-center"
                    style={landing.image_url ? { backgroundImage: `url(${landing.image_url})` } : undefined}
                    role={landing.image_url ? 'img' : undefined}
                    aria-label={landing.image_url ? landing.title : undefined}
                />
            </section>

            {products.length > 0 && (
                <section className="border-t border-black/10 bg-white py-16 lg:py-24">
                    <div className="mx-auto max-w-[1200px] px-6 lg:px-8">
                        <div className="flex items-end justify-between gap-6">
                            <div>
                                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-black/45">Подборка</p>
                                <h2 className="mt-3 text-3xl font-semibold tracking-[-0.04em] sm:text-4xl">Изделия автора</h2>
                            </div>
                            <Link href="/" className="hidden text-sm font-semibold underline underline-offset-4 sm:block">Весь каталог</Link>
                        </div>
                        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                            {products.map(product => (
                                <Link key={product.id} href={`/product/${product.id}`} className="group block">
                                    <div
                                        className="aspect-[4/5] rounded-2xl bg-[#eeeeea] bg-cover bg-center transition duration-300 group-hover:opacity-85"
                                        style={product.desktop_video_poster || product.mobile_card_image
                                            ? { backgroundImage: `url(${product.desktop_video_poster || product.mobile_card_image})` }
                                            : undefined}
                                    />
                                    <div className="mt-4 flex items-start justify-between gap-4 text-sm">
                                        <h3 className="font-medium">{product.title}</h3>
                                        <p className="whitespace-nowrap font-semibold">{product.price.toLocaleString('ru-RU')} ₽</p>
                                    </div>
                                </Link>
                            ))}
                        </div>
                    </div>
                </section>
            )}

            <section className="bg-[#181818] py-16 text-white lg:py-24">
                <div className="mx-auto max-w-[900px] px-6 text-center lg:px-8">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/45">GARMENT BURO</p>
                    <h2 className="mt-5 text-3xl font-semibold tracking-[-0.04em] sm:text-5xl">Соберите вещь под себя</h2>
                    <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-white/55">
                        Выберите основу, посадку и детали. Мы изготовим изделие и доставим его вам.
                    </p>
                    <Link href={landing.cta_href} className="mt-8 inline-flex h-12 items-center justify-center rounded-xl bg-white px-6 text-sm font-semibold text-black transition hover:bg-white/80">
                        {landing.cta_label}
                    </Link>
                </div>
            </section>
        </main>
    </div>
);
