import { createCatalogEditorClient } from '@/lib/products/editorClient';
import {
    assortmentRequest,
    uploadAssortmentMedia,
} from '@/lib/api/productionAssortment';
import { useProductionAuthStore } from '@/store/productionAuthStore';
import { readPresetUpload } from '@/lib/products/editorReads';

const productionRequest = async <T>(
    operation: (token: string) => Promise<T>,
): Promise<T> => {
    const owner = useProductionAuthStore.getState().user?.id;
    if (!owner) throw new DOMException('Сессия завершена.', 'AbortError');
    const result = await useProductionAuthStore
        .getState()
        .runAuthenticated(operation);
    if (owner !== useProductionAuthStore.getState().user?.id)
        throw new DOMException('Сессия изменилась.', 'AbortError');
    return result;
};
export const productionEditorClient = createCatalogEditorClient({
    base: '/production/admin/assortment',
    options: '/production/admin/assortment/editor-options',
    authorize: productionRequest,
    upload: (file) =>
        productionRequest(async () => {
            const media = await uploadAssortmentMedia(file, 'public');
            return readPresetUpload(media);
        }),
});

export const deleteProductionProduct = (id: number) =>
    productionRequest(() =>
        assortmentRequest(`products/${id}`, { method: 'DELETE' }),
    );
