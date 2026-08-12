import type { CdekTestController } from '@/hooks/cdek/useCdekTestPage';
import { getAddressSuggestionLabel, getOfficeAddress, getOfficeTitle } from '@/lib/cdek/utils/cdek';
import { CdekYandexMap } from './CdekYandexMap';

export const CdekOfficeResults = ({ controller }: { controller: CdekTestController }) => (
    <div className="rounded-[28px] border border-black/10 bg-[#FCFCF8] p-4 shadow-sm md:p-5">
        <div className="mb-4 grid gap-3 md:grid-cols-[1fr_auto]">
            <div className="relative">
                <input
                    value={controller.query}
                    onChange={(event) => controller.changeQuery(event.target.value)}
                    className="h-12 w-full rounded-2xl border border-black/10 bg-white px-4 text-[14px] outline-none transition placeholder:text-black/35 focus:border-black"
                    placeholder="Введите адрес, улицу, метро или код ПВЗ"
                />
                {(controller.addressSuggestions.length > 0 || controller.suggestState === 'loading') && (
                    <div className="absolute left-0 right-0 top-[56px] z-30 overflow-hidden rounded-3xl border border-black/10 bg-white shadow-[0_18px_50px_rgba(0,0,0,0.14)]">
                        {controller.suggestState === 'loading' && controller.addressSuggestions.length === 0 ? (
                            <div className="px-4 py-3 text-[13px] text-black/45">Ищу адрес...</div>
                        ) : controller.addressSuggestions.map((suggestion, index) => {
                            const label = getAddressSuggestionLabel(suggestion);
                            return (
                                <button
                                    key={`${label}-${index}`}
                                    type="button"
                                    onMouseDown={(event) => event.preventDefault()}
                                    onClick={() => controller.selectSuggestion(suggestion)}
                                    className="block w-full border-b border-black/5 px-4 py-3 text-left text-[13px] leading-snug text-black transition last:border-b-0 hover:bg-[#F2F2F2]"
                                >
                                    {label}
                                </button>
                            );
                        })}
                    </div>
                )}
            </div>
            <div className="flex h-12 items-center rounded-2xl border border-black/10 bg-white px-4 text-[13px] text-black/55">
                {controller.searchCenter ? 'Ближайшие' : 'Показано'}: {controller.filteredOffices.length} / {controller.offices.length}
            </div>
        </div>

        <CdekYandexMap
            offices={controller.filteredOffices}
            selectedCode={controller.selectedCode}
            searchCenter={controller.searchCenter}
            selectedAddressLabel={controller.selectedAddressLabel}
            onSelect={controller.setSelectedCode}
        />

        <div className="grid max-h-[560px] gap-3 overflow-y-auto pr-1 md:grid-cols-2">
            {controller.loadState === 'loading' && Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="h-[146px] animate-pulse rounded-3xl bg-white" />
            ))}
            {controller.loadState !== 'loading' && controller.filteredOffices.map((office) => {
                const isActive = office.code === controller.selectedCode;
                return (
                    <button
                        key={office.code}
                        type="button"
                        onClick={() => controller.setSelectedCode(office.code)}
                        className={`rounded-3xl border p-4 text-left transition ${isActive
                            ? 'border-black bg-black text-white'
                            : 'border-black/10 bg-white text-black hover:border-black/35'}`}
                    >
                        <div className="mb-3 flex items-center justify-between gap-3">
                            <span className={`rounded-full px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] ${isActive ? 'bg-white text-black' : 'bg-black text-white'}`}>
                                {office.type || 'PVZ'}
                            </span>
                            <span className={isActive ? 'text-[11px] text-white/55' : 'text-[11px] text-black/40'}>{office.code}</span>
                        </div>
                        <h2 className="line-clamp-2 text-[15px] font-semibold leading-tight">{getOfficeTitle(office)}</h2>
                        <p className={`mt-2 line-clamp-2 text-[13px] leading-snug ${isActive ? 'text-white/75' : 'text-black/60'}`}>{getOfficeAddress(office)}</p>
                        <p className={`mt-3 text-[12px] ${isActive ? 'text-white/50' : 'text-black/45'}`}>{office.work_time || 'График не указан'}</p>
                    </button>
                );
            })}
        </div>
    </div>
);
