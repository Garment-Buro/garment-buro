"use client";

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

import { getProducts } from '@/lib/api/products';
import type { CatalogSection } from '@/lib/catalog/types';
import {
    createCatalogSectionUpdate,
    getActiveCatalogCartItem,
    getOrderedCatalogProducts,
    selectCatalogProducts,
} from '@/lib/catalog/utils/catalog';
import type { CatalogProduct } from '@/lib/products/types';
import type { LandingSettings } from '@/lib/settings/types';
import { isMockDataEnabled } from '@/lib/runtime/config';
import { useCartStore } from '@/store/cartStore';
import { useSettingsStore } from '@/store/settingsStore';

type UseCatalogPageOptions = {
    initialProducts: CatalogProduct[];
    initialSettings: LandingSettings | null;
};

export const useCatalogPage = ({ initialProducts, initialSettings }: UseCatalogPageOptions) => {
    const router = useRouter();
    const [products, setProducts] = useState(initialProducts);
    const [isConstructorHintOpen, setIsConstructorHintOpen] = useState(false);
    const { settings: storeSettings, fetchSettings, updateSettings } = useSettingsStore();
    const { items, activeItemId } = useCartStore();
    const settings = storeSettings || initialSettings;

    useEffect(() => {
        if (!initialSettings) void fetchSettings();
    }, [fetchSettings, initialSettings]);

    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const frame = window.requestAnimationFrame(() => {
            setIsConstructorHintOpen(params.get('selectForConstructor') === '1');
        });
        return () => window.cancelAnimationFrame(frame);
    }, []);

    useEffect(() => {
        if (initialProducts.length > 0 || isMockDataEnabled()) return;

        const controller = new AbortController();
        getProducts(controller.signal)
            .then(setProducts)
            .catch(error => {
                if (!controller.signal.aborted) console.error('Failed to fetch products:', error);
            });
        return () => controller.abort();
    }, [initialProducts.length]);

    const sections = useMemo(() => {
        if (!settings) return null;
        const heroProducts = selectCatalogProducts(products, settings.hero_products);
        const showroom1 = selectCatalogProducts(products, settings.showroom1_products);
        const showroom2 = selectCatalogProducts(products, settings.showroom2_products);
        return { heroProducts, showroom1, showroom2 };
    }, [products, settings]);

    const orderedProducts = useMemo(() => sections
        ? getOrderedCatalogProducts(products, [sections.heroProducts, sections.showroom1, sections.showroom2])
        : [], [products, sections]);

    const landingCartItem = useMemo(
        () => getActiveCatalogCartItem(items, activeItemId),
        [activeItemId, items],
    );

    const goToCheckout = useCallback(() => {
        if (items.length > 0) router.push('/checkout');
    }, [items.length, router]);

    const editCartItem = useCallback(() => {
        if (!landingCartItem) return;
        router.push(`/constructor?productId=${landingCartItem.product_id}&editCartItemId=${encodeURIComponent(landingCartItem.id)}`);
    }, [landingCartItem, router]);

    const replaceProductSlot = useCallback((section: CatalogSection, index: number) => {
        if (!settings) return;
        const nextId = window.prompt('Введите новый ID товара для этого слота:');
        if (!nextId) return;
        const productId = Number.parseInt(nextId, 10);
        if (Number.isNaN(productId)) return;
        void updateSettings(createCatalogSectionUpdate(settings, section, index, productId));
    }, [settings, updateSettings]);

    return {
        settings,
        sections,
        orderedProducts,
        isConstructorHintOpen,
        landingCartItem,
        hasCartItems: items.length > 0,
        closeConstructorHint: () => {
            setIsConstructorHintOpen(false);
            router.replace('/', { scroll: false });
        },
        goBack: () => router.back(),
        goToCheckout,
        editCartItem,
        replaceProductSlot,
    };
};
