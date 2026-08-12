import { VariantCard } from '@/components/admin/VariantCard';
import { ProductFormSection } from '@/components/admin/product-form/ProductFormSection';
import { Button } from '@/components/shared/Button';
import { Input } from '@/components/shared/Input';
import { Text } from '@/components/shared/Text';
import type { useAdminProductForm } from '@/hooks/admin/useAdminProductForm';

type Controller = ReturnType<typeof useAdminProductForm>;

export function AdminProductDetailsSections({ controller }: { controller: Controller }) {
    const { form, setField, addVariant, changeVariant, removeVariant } = controller;

    return (
        <>
            <ProductFormSection title="Основная информация">
                <div><Text size={14} className="mb-2">Название</Text><Input value={form.title} onChange={event => setField('title', event.target.value)} required /></div>
                <div>
                    <Text size={14} className="mb-2">Описание</Text>
                    <textarea value={form.description} onChange={event => setField('description', event.target.value)} className="w-full min-h-[100px] p-4 rounded-[13.3px] bg-[#F3F3F3] border border-transparent focus:border-black outline-none font-manrope text-[14px]" />
                </div>
                <div className="flex gap-4">
                    <div className="flex-1"><Text size={14} className="mb-2">Цена</Text><Input type="number" value={form.price} onChange={event => setField('price', event.target.value)} required /></div>
                    <div className="flex-1"><Text size={14} className="mb-2">Старая цена</Text><Input type="number" value={form.oldPrice} onChange={event => setField('oldPrice', event.target.value)} /></div>
                </div>
            </ProductFormSection>

            <ProductFormSection title="Логистика" gap="compact">
                <div><Text size={14} className="mb-2">Вес (кг, для СДЭК)</Text><Input type="number" step="0.01" value={form.weight} onChange={event => setField('weight', event.target.value)} required /></div>
                <div>
                    <Text size={14} className="mb-2">Габариты (см): Высота х Ширина х Длина</Text>
                    <div className="flex gap-4">
                        <Input type="number" placeholder="В" value={form.height} onChange={event => setField('height', event.target.value)} />
                        <Input type="number" placeholder="Ш" value={form.width} onChange={event => setField('width', event.target.value)} />
                        <Input type="number" placeholder="Д" value={form.length} onChange={event => setField('length', event.target.value)} />
                    </div>
                </div>
            </ProductFormSection>

            <ProductFormSection title="Склад" gap="compact">
                <div className="flex gap-4"><div className="flex-1"><Text size={14} className="mb-2">Общий остаток (запасной)</Text><Input type="number" value={form.stockQuantity} onChange={event => setField('stockQuantity', event.target.value)} /></div></div>
            </ProductFormSection>

            <section className="flex flex-col gap-4">
                <div className="flex justify-between items-center border-b pb-2">
                    <Text size={18} weight="semibold">Вариации</Text>
                    <Button type="button" onClick={addVariant} className="bg-black text-white text-[12px] h-[32px] px-4">+ Добавить вариацию</Button>
                </div>
                {form.variants.length === 0 ? (
                    <div className="text-center py-10 text-black/30 border-2 border-dashed border-black/10 rounded-[16px]"><p className="text-[14px]">Нет вариаций. Нажмите «Добавить вариацию».</p></div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {form.variants.map((variant, index) => <VariantCard key={variant.id ?? index} index={index} variant={variant} onChange={changeVariant} onRemove={removeVariant} />)}
                    </div>
                )}
            </section>
        </>
    );
}
