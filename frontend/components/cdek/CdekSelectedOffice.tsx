import type { CdekTestController } from '@/hooks/cdek/useCdekTestPage';
import { formatCdekPrice, getOfficeAddress, getOfficeTitle } from '@/lib/cdek/utils/cdek';

export const CdekSelectedOffice = ({ controller }: { controller: CdekTestController }) => (
    <aside className="h-fit rounded-[28px] border border-black/10 bg-black p-5 text-white shadow-[0_24px_70px_rgba(0,0,0,0.16)] md:sticky md:top-6">
        <p className="mb-4 text-[11px] uppercase tracking-[0.28em] text-white/45">selected point</p>
        {controller.selectedOffice ? (
            <div>
                <h2 className="text-[26px] font-semibold leading-[1] tracking-[-0.05em]">{getOfficeTitle(controller.selectedOffice)}</h2>
                <p className="mt-4 text-[14px] leading-relaxed text-white/70">{getOfficeAddress(controller.selectedOffice)}</p>
                <div className="mt-5 space-y-3 rounded-3xl border border-white/10 bg-white/8 p-4 text-[13px] text-white/70">
                    <div className="flex justify-between gap-4"><span>Код ПВЗ</span><strong className="text-white">{controller.selectedOffice.code}</strong></div>
                    <div className="flex justify-between gap-4"><span>Город</span><strong className="text-right text-white">{controller.selectedOffice.location?.city || '-'}</strong></div>
                    <div className="flex justify-between gap-4"><span>Время работы</span><strong className="text-right text-white">{controller.selectedOffice.work_time || '-'}</strong></div>
                    {controller.selectedOffice.nearest_station && (
                        <div className="flex justify-between gap-4"><span>Ориентир</span><strong className="text-right text-white">{controller.selectedOffice.nearest_station}</strong></div>
                    )}
                </div>
                <button
                    type="button"
                    onClick={controller.calculateTariff}
                    disabled={controller.tariffState === 'loading'}
                    className="mt-5 h-13 w-full rounded-full bg-[#D6FF58] text-[12px] font-semibold uppercase tracking-[0.16em] text-black transition hover:bg-[#c6f04a] disabled:cursor-wait disabled:opacity-70"
                >
                    {controller.tariffState === 'loading' ? 'считаю тариф' : 'посчитать доставку'}
                </button>
                {controller.tariff && (
                    <div className="mt-4 rounded-3xl bg-[#FCFCF8] p-4 text-black">
                        <p className="text-[12px] uppercase tracking-[0.18em] text-black/45">delivery price</p>
                        <p className="mt-2 text-[34px] font-semibold tracking-[-0.06em]">{formatCdekPrice(controller.tariff.delivery_sum || 0)} ₽</p>
                        {(controller.tariff.period_min || controller.tariff.period_max) && (
                            <p className="mt-1 text-[13px] text-black/55">
                                Срок: {controller.tariff.period_min || controller.tariff.period_max}-{controller.tariff.period_max || controller.tariff.period_min} дн.
                            </p>
                        )}
                    </div>
                )}
                {controller.tariffState === 'error' && (
                    <p className="mt-4 rounded-2xl border border-red-300/40 bg-red-500/10 p-3 text-[13px] text-red-100">
                        Не удалось посчитать тариф через API. Сам выбор ПВЗ при этом работает.
                    </p>
                )}
            </div>
        ) : (
            <div className="rounded-3xl border border-white/10 bg-white/8 p-5 text-[14px] leading-relaxed text-white/65">
                Выберите пункт на схеме или в списке. Здесь появится адрес, код ПВЗ и тестовый расчет доставки.
            </div>
        )}
    </aside>
);
