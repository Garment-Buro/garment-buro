import type { CdekTestController } from '@/hooks/cdek/useCdekTestPage';
import { CITY_PRESETS } from '@/lib/cdek/data';

export const CdekLabHeader = ({ controller }: { controller: CdekTestController }) => (
    <section className="overflow-hidden rounded-[30px] border border-black/10 bg-[#FCFCF8] shadow-[0_24px_90px_rgba(0,0,0,0.08)]">
        <div className="grid gap-0 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="relative min-h-[320px] bg-black p-7 text-[#FCFCF8] md:p-10">
                <div className="absolute inset-0 opacity-70 [background:radial-gradient(circle_at_20%_10%,rgba(255,255,255,0.28),transparent_28%),radial-gradient(circle_at_70%_80%,rgba(252,252,248,0.16),transparent_30%)]" />
                <div className="relative z-10 flex h-full flex-col justify-between gap-10">
                    <div>
                        <p className="mb-4 text-[11px] uppercase tracking-[0.36em] text-white/55">custom cdek lab</p>
                        <h1 className="max-w-[560px] text-[34px] font-semibold leading-[0.96] tracking-[-0.06em] md:text-[58px]">
                            Быстрый свой выбор ПВЗ без стандартного виджета
                        </h1>
                    </div>
                    <div className="grid gap-3 text-[13px] leading-relaxed text-white/70 md:grid-cols-3">
                        <div className="rounded-2xl border border-white/10 bg-white/8 p-4 backdrop-blur">
                            <strong className="mb-1 block text-white">1. Легкий старт</strong>Не грузим внешний CDEK widget.
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-white/8 p-4 backdrop-blur">
                            <strong className="mb-1 block text-white">2. Наш API</strong>ПВЗ идут через кешируемый прокси.
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-white/8 p-4 backdrop-blur">
                            <strong className="mb-1 block text-white">3. UX под нас</strong>Поиск, список и выбор контролируем сами.
                        </div>
                    </div>
                </div>
            </div>

            <div className="p-5 md:p-8">
                <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                    <div className="grid gap-2 sm:grid-cols-3">
                        {CITY_PRESETS.map((city) => (
                            <button
                                key={city.code}
                                type="button"
                                onClick={() => controller.selectCity(city.code)}
                                className={`h-11 rounded-full border px-4 text-[13px] transition ${controller.cityCode === city.code
                                    ? 'border-black bg-black text-white'
                                    : 'border-black/10 bg-white text-black hover:border-black/40'}`}
                            >
                                {city.label}
                            </button>
                        ))}
                    </div>
                    <div className="flex gap-2">
                        <input
                            value={controller.manualCityCode}
                            onChange={(event) => controller.setManualCityCode(event.target.value)}
                            className="h-11 w-24 rounded-full border border-black/10 bg-white px-4 text-center text-[13px] outline-none focus:border-black"
                            placeholder="код"
                        />
                        <button
                            type="button"
                            onClick={controller.applyManualCityCode}
                            className="h-11 rounded-full bg-[#D6FF58] px-5 text-[12px] font-semibold uppercase tracking-[0.14em] text-black transition hover:bg-[#c6f04a]"
                        >
                            загрузить
                        </button>
                    </div>
                </div>
                <div className="mt-4 rounded-2xl border border-black/10 bg-white p-4 text-[13px] text-black/65">
                    <div className="flex flex-wrap items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${controller.loadState === 'loading' ? 'bg-amber-500' : controller.loadState === 'ready' ? 'bg-emerald-500' : controller.loadState === 'error' ? 'bg-orange-500' : 'bg-black/30'}`} />
                        <span>{controller.message}</span>
                        {controller.isDemo && <span className="rounded-full bg-orange-100 px-2 py-1 text-[11px] uppercase tracking-[0.12em] text-orange-700">demo</span>}
                    </div>
                </div>
            </div>
        </div>
    </section>
);
