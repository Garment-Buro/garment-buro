import { ProductFormSection } from '@/components/admin/product-form/ProductFormSection';
import { ProductMediaField } from '@/components/admin/product-form/ProductMediaField';
import type { useAdminProductForm } from '@/hooks/admin/useAdminProductForm';

type Controller = ReturnType<typeof useAdminProductForm>;
type MultiMediaField = 'desktopCardImages' | 'desktopSliderImages' | 'mobileSliderImages' | 'mobileProductSliderImages';

export function AdminProductMediaSections({ controller }: { controller: Controller }) {
    const { form, setField, uploadFile, uploadFiles } = controller;
    const removeAt = (field: MultiMediaField, index: number) => setField(field, form[field].filter((_, itemIndex) => itemIndex !== index));

    const single = (field: Parameters<typeof uploadFile>[1]) => ({ value: form[field], onChange: (event: Parameters<typeof uploadFile>[0]) => uploadFile(event, field) });
    const multiple = (field: MultiMediaField) => ({ value: form[field], onChange: (event: Parameters<typeof uploadFiles>[0]) => uploadFiles(event, field), onRemove: (index: number) => removeAt(field, index) });

    return (
        <>
            <ProductFormSection title="Десктопная версия" tone="desktop">
                <ProductMediaField label="Видео (.mp4)" accept="video/mp4" preview="video" {...single('desktopVideo')} />
                <ProductMediaField label="Обложка для видео (Desktop)" description="Показывается на лендинге до наведения, пока видео не загрузилось" {...single('desktopVideoPoster')} />
                <ProductMediaField label="Фото в корзине" {...multiple('desktopCardImages')} />
                <ProductMediaField label="Фото слайдера" {...multiple('desktopSliderImages')} />
            </ProductFormSection>

            <ProductFormSection title="Мобильная версия" tone="mobile">
                <ProductMediaField label="Фото слева (Блок 2 - Модель)" {...single('mobileCardImage')} />
                <ProductMediaField label="Обложка для видео (Mobile)" description="Показывается на лендинге слева, пока видео не загрузилось" {...single('mobileVideoPoster')} />
                <ProductMediaField label="Фото слайдера в каталоге (Mobile)" description="Показывается в карточке товара на лендинге при свайпе" {...multiple('mobileSliderImages')} />
                <ProductMediaField label="Фото слайдера на странице товара (Mobile)" description="Показывается на странице товара при свайпе. Если пусто — используется слайдер каталога" {...multiple('mobileProductSliderImages')} />
                <ProductMediaField label="Фото справа от размеров (Блок 1)" {...single('mobileSizeChartFirst')} />
            </ProductFormSection>

            <ProductFormSection title="Размерная сетка">
                <div className="flex gap-4">
                    <div className="flex-1"><ProductMediaField label="Схема изделия" preview="contain" {...single('sizeChartImg1')} /></div>
                    <div className="flex-1"><ProductMediaField label="Размерная сетка" preview="contain" {...single('sizeChartImg2')} /></div>
                </div>
            </ProductFormSection>
        </>
    );
}
