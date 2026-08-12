import { CdekMap } from '@/components/checkout/CdekMap';
import { Text } from '@/components/shared/Text';
import type { CheckoutController } from '@/hooks/checkout/useCheckout';

function CdekLoadingSkeleton() {
    return (
        <phantom-ui loading animation="shimmer" reveal={0.2}>
            <div className="relative w-full h-[500px] rounded-lg overflow-hidden border border-black/10 bg-[#FAFAFA] p-5">
                <div className="flex justify-between items-center mb-6"><div className="w-[40%] max-w-[200px] h-7 bg-[#E5E5E5] rounded-lg" /><div className="w-[30%] max-w-[120px] h-7 bg-[#E5E5E5] rounded-lg" /></div>
                <div className="w-full h-[45px] bg-[#E5E5E5] rounded-xl mb-6" />
                <div className="w-full h-[350px] bg-[#E5E5E5]/60 rounded-xl" />
            </div>
        </phantom-ui>
    );
}

function CdekMessage({ error, onRetry }: { error?: boolean; onRetry: () => void }) {
    return (
        <div className="w-full h-[500px] flex flex-col items-center justify-center gap-4 bg-[#F7F7F7] rounded-lg border border-black/10 px-6 text-center">
            <Text size={14} className="text-[#777]">
                {error ? 'Не удалось загрузить карту СДЭК. Проверьте соединение и попробуйте снова.' : 'Карта СДЭК загрузится, когда вы перейдете к выбору доставки.'}
            </Text>
            <button type="button" onClick={onRetry} className="h-[42px] px-5 rounded-[10px] bg-black text-white text-[13px] uppercase tracking-wide hover:bg-black/85 transition-colors">
                {error ? 'повторить' : 'выбрать доставку'}
            </button>
        </div>
    );
}

export function CheckoutDeliverySection({ controller }: { controller: CheckoutController }) {
    const { form, errors, deliveryWidgetRef, cdekScriptLoaded, cdekGoods, cdekLoadState, chooseCdek, setDeliveryPrice, ensureCdekLoad, clearCdekSelection } = controller;
    return (
        <div className="flex flex-col gap-6 mt-8">
            <Text size={20} className="mb-2 ml-1">Доставка</Text>
            <Text size={12} className="text-[#7A7A7A] ml-1">Выберите город, тип доставки и адрес прямо в виджете СДЭК ниже.</Text>
            <div className="mt-2" ref={deliveryWidgetRef}>
                {form.cdekAddress && (
                    <div className="mb-3 p-3 bg-white/60 rounded-md border border-black/10 flex items-start justify-between gap-3">
                        <div><Text size={12} className="text-[#7A7A7A] mb-1">Выбрано в СДЭК</Text><Text size={13} className="text-[#000000]">{form.cdekAddress}</Text></div>
                        <button type="button" onClick={clearCdekSelection} className="text-[12px] text-[#666] hover:text-black whitespace-nowrap">Изменить выбор</button>
                    </div>
                )}
                {errors.deliveryAddress && <Text size={12} className="text-red-500 mb-2">Выберите доставку в виджете СДЭК</Text>}
                {cdekScriptLoaded ? <CdekMap cdekScriptLoaded goods={cdekGoods} onChoose={chooseCdek} onCalculate={setDeliveryPrice} />
                    : cdekLoadState === 'idle' ? <CdekMessage onRetry={ensureCdekLoad} />
                        : cdekLoadState === 'error' ? <CdekMessage error onRetry={ensureCdekLoad} />
                            : <CdekLoadingSkeleton />}
            </div>
        </div>
    );
}
