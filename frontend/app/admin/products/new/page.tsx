"use client";

import { AdminProductDetailsSections } from '@/components/admin/product-form/AdminProductDetailsSections';
import { AdminProductMediaSections } from '@/components/admin/product-form/AdminProductMediaSections';
import { Button } from '@/components/shared/Button';
import { Container } from '@/components/shared/Container';
import { Text } from '@/components/shared/Text';
import { useAdminProductForm } from '@/hooks/admin/useAdminProductForm';

export default function ProductFormPage() {
    const controller = useAdminProductForm();

    if (controller.loading) {
        return <Container className="pt-32"><Text>Загрузка...</Text></Container>;
    }

    return (
        <Container className="pt-32 pb-20 min-h-screen text-black">
            <Text size={24} weight="semibold" className="mb-10">
                {controller.isEditMode ? 'Редактировать товар' : 'Добавить товар'}
            </Text>

            <form onSubmit={controller.submit} className="max-w-4xl flex flex-col gap-10">
                <AdminProductDetailsSections controller={controller} />
                <AdminProductMediaSections controller={controller} />

                <div className="flex gap-4 mt-4 pb-16">
                    <Button type="button" variant="secondary" onClick={controller.cancel} className="px-8 border border-black/20 text-black bg-white hover:bg-gray-100 h-[50px]">
                        Отмена
                    </Button>
                    <Button type="submit" disabled={controller.saving} className="px-8 bg-black text-white hover:bg-gray-800 h-[50px] disabled:opacity-50">
                        {controller.saving ? 'Сохранение...' : 'Сохранить товар'}
                    </Button>
                </div>
            </form>
        </Container>
    );
}
