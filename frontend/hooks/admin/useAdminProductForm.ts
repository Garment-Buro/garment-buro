'use client';

import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react';
import { useParams, useRouter } from 'next/navigation';

import { ApiError } from '@/lib/api/http';
import { getAdminProduct, saveAdminProduct } from '@/lib/api/products';
import { uploadMediaFile } from '@/lib/api/uploads';
import type { ProductVariantData } from '@/lib/products/types';
import {
    createAdminProductPayload,
    createEmptyProductVariant,
    EMPTY_ADMIN_PRODUCT_FORM,
    mapAdminProductToForm,
    type AdminProductFormValues,
} from '@/lib/products/utils/productForm';
import { useVariantOptionsStore } from '@/store/variantOptionsStore';
import { runCatalogWrite } from '@/store/catalogWrite';

type SingleMediaField = 'desktopVideo' | 'desktopVideoPoster' | 'mobileCardImage' | 'mobileVideoPoster'
    | 'mobileSizeChartFirst' | 'sizeChartImg1' | 'sizeChartImg2';
type MultiMediaField = 'desktopCardImages' | 'desktopSliderImages' | 'mobileSliderImages' | 'mobileProductSliderImages';

export const useAdminProductForm = () => {
    const router = useRouter();
    const params = useParams();
    const productId = typeof params.id === 'string' ? params.id : null;
    const isEditMode = productId !== null;
    const [form, setForm] = useState<AdminProductFormValues>(EMPTY_ADMIN_PRODUCT_FORM);
    const [loading, setLoading] = useState(isEditMode);
    const [saving, setSaving] = useState(false);
    const fetchOptions = useVariantOptionsStore((state) => state.fetchOptions);

    useEffect(() => {
        void fetchOptions();
        if (!productId) return;

        const controller = new AbortController();
        getAdminProduct(productId, controller.signal)
            .then((product) => setForm(mapAdminProductToForm(product)))
            .catch((error: unknown) => {
                if (!controller.signal.aborted) console.error(error);
            })
            .finally(() => {
                if (!controller.signal.aborted) setLoading(false);
            });
        return () => controller.abort();
    }, [fetchOptions, productId]);

    const setField = <Key extends keyof AdminProductFormValues>(key: Key, value: AdminProductFormValues[Key]) => {
        setForm((current) => ({ ...current, [key]: value }));
    };

    const uploadFile = async (event: ChangeEvent<HTMLInputElement>, field: SingleMediaField) => {
        const file = event.target.files?.[0];
        if (!file) return;
        try {
            setField(field, await runCatalogWrite(token => uploadMediaFile(file, token)));
        } catch (error) {
            console.error(error);
        }
    };

    const uploadFiles = async (event: ChangeEvent<HTMLInputElement>, field: MultiMediaField) => {
        const files = Array.from(event.target.files || []);
        const uploaded: string[] = [];
        for (const file of files) {
            try {
                uploaded.push(await runCatalogWrite(token => uploadMediaFile(file, token)));
            } catch (error) {
                console.error(error);
            }
        }
        setField(field, [...form[field], ...uploaded]);
    };

    const addVariant = () => setField('variants', [...form.variants, createEmptyProductVariant()]);
    const changeVariant = (index: number, variant: ProductVariantData) => {
        const variants = [...form.variants];
        variants[index] = variant;
        setField('variants', variants);
    };
    const removeVariant = (index: number) => setField('variants', form.variants.filter((_, itemIndex) => itemIndex !== index));

    const submit = async (event: FormEvent) => {
        event.preventDefault();
        setSaving(true);
        try {
            await runCatalogWrite(token => (
                saveAdminProduct(productId, createAdminProductPayload(form), token)
            ));
            router.push('/admin');
        } catch (error) {
            if (error instanceof ApiError) alert('Ошибка при сохранении');
            console.error(error);
        } finally {
            setSaving(false);
        }
    };

    const cancel = () => router.push('/admin');

    return { form, setField, loading, saving, isEditMode, uploadFile, uploadFiles, addVariant, changeVariant, removeVariant, submit, cancel };
};
