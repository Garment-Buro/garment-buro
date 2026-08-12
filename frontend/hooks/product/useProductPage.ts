"use client";

import type { FormEvent } from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';

import { getProduct, getProducts } from '@/lib/api/products';
import type { ProductData } from '@/lib/products/types';
import {
    fillReviewImages,
    getNextProducts,
    getPreferredVariant,
    getProductCartImage,
    getProductVariantPresentation,
    getRelatedProductPages,
    getReviewPreviewImages,
    localizeProductColor,
    normalizeProductDescription,
} from '@/lib/products/utils/product';
import { useCartStore } from '@/store/cartStore';

type WaitlistData = {
    name: string;
    email: string;
    phone: string;
};

const EMPTY_WAITLIST_DATA: WaitlistData = { name: '', email: '', phone: '' };

export const useProductPage = (initialProduct: ProductData, initialProducts: ProductData[]) => {
    const params = useParams();
    const router = useRouter();
    const productId = params?.id ? Number(params.id) : initialProduct.id;
    const preferredInitialVariant = getPreferredVariant(initialProduct);
    const [product, setProduct] = useState<ProductData | null>(initialProduct);
    const [allProducts, setAllProducts] = useState(initialProducts);
    const [loadedImagesCount, setLoadedImagesCount] = useState(1);
    const [selectedColor, setSelectedColor] = useState(preferredInitialVariant?.color || '');
    const [selectedSize, setSelectedSize] = useState(preferredInitialVariant?.size || '');
    const [showSizeChart, setShowSizeChart] = useState(false);
    const [relatedSlideIndex, setRelatedSlideIndex] = useState(0);
    const [activeDesktopImg, setActiveDesktopImg] = useState(0);
    const [showWaitlistForm, setShowWaitlistForm] = useState(false);
    const [waitlistSent, setWaitlistSent] = useState(false);
    const [waitlistData, setWaitlistData] = useState<WaitlistData>(EMPTY_WAITLIST_DATA);
    const [hasScrolled, setHasScrolled] = useState(false);
    const { items, addItem } = useCartStore();

    useEffect(() => {
        const handleScroll = () => setHasScrolled(window.scrollY > 200);
        window.addEventListener('scroll', handleScroll, { passive: true });
        handleScroll();
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    useEffect(() => {
        if (!productId) return;
        const controller = new AbortController();
        let relatedTimeout: ReturnType<typeof setTimeout> | undefined;
        let relatedIdleId: number | undefined;

        const loadRelatedProducts = async () => {
            try {
                const products = await getProducts(controller.signal);
                if (!controller.signal.aborted) {
                    setRelatedSlideIndex(0);
                    setAllProducts([...products].sort((first, second) => first.id - second.id));
                }
            } catch (error) {
                if (!controller.signal.aborted) console.error('Failed to fetch related products:', error);
            }
        };

        const scheduleRelatedProducts = () => {
            if (initialProducts.length > 0) return;
            const loadRelated = () => {
                if (!controller.signal.aborted) void loadRelatedProducts();
            };
            if ('requestIdleCallback' in window) {
                relatedIdleId = window.requestIdleCallback(loadRelated, { timeout: 1500 });
            } else {
                relatedTimeout = setTimeout(loadRelated, 700);
            }
        };

        getProduct(productId, controller.signal)
            .then(data => {
                if (controller.signal.aborted) return;
                setProduct(data);
                setRelatedSlideIndex(0);
                const preferredVariant = getPreferredVariant(data);
                setSelectedColor(preferredVariant?.color || '');
                setSelectedSize(preferredVariant?.size || '');
            })
            .catch(error => {
                if (!controller.signal.aborted) console.error('Failed to fetch product:', error);
            })
            .finally(() => {
                if (!controller.signal.aborted) scheduleRelatedProducts();
            });

        return () => {
            if (relatedTimeout) clearTimeout(relatedTimeout);
            if (relatedIdleId && 'cancelIdleCallback' in window) window.cancelIdleCallback(relatedIdleId);
            controller.abort();
        };
    }, [initialProducts.length, productId]);

    useEffect(() => {
        if (!product || document.querySelectorAll('.desktop-slider-img').length === 0) return;
        const observer = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                const imageIndex = Number(entry.target.getAttribute('data-index'));
                if (!Number.isNaN(imageIndex)) setActiveDesktopImg(imageIndex);
            });
        }, { threshold: 0.5, rootMargin: '-100px 0px -20% 0px' });
        document.querySelectorAll('.desktop-slider-img').forEach(element => observer.observe(element));
        return () => observer.disconnect();
    }, [product, selectedColor]);

    const variantPresentation = useMemo(
        () => getProductVariantPresentation(product, selectedColor, selectedSize),
        [product, selectedColor, selectedSize],
    );
    const currentProductId = product?.id;
    const reviewImagesToRender = useMemo(
        () => fillReviewImages(getReviewPreviewImages(allProducts, currentProductId)),
        [allProducts, currentProductId],
    );
    const nextProducts = useMemo(
        () => getNextProducts(allProducts, currentProductId),
        [allProducts, currentProductId],
    );
    const relatedProductPages = useMemo(
        () => getRelatedProductPages(allProducts),
        [allProducts],
    );

    const currentCartColor = localizeProductColor(selectedColor);
    const currentProductCartItem = product
        ? items.find(item => item.id === `${product.id}_${selectedSize}_${currentCartColor}`)
        : undefined;
    const normalizedProductDescription = product?.description
        ? normalizeProductDescription(product.description)
        : '';

    const addProductToCart = useCallback((quantity = 1) => {
        if (!product) return;
        addItem({
            product_id: product.id,
            title: product.title,
            price: product.price,
            image: getProductCartImage(product),
            size: selectedSize,
            color: localizeProductColor(selectedColor),
            quantity,
        });
    }, [addItem, product, selectedColor, selectedSize]);

    const handleProductBack = useCallback(() => {
        if (window.history.length > 1) {
            router.back();
            return;
        }
        router.push('/');
    }, [router]);

    const handleMobileAddClick = useCallback(() => {
        if (variantPresentation.currentStock === 0) {
            setShowWaitlistForm(true);
            return;
        }
        addProductToCart(1);
    }, [addProductToCart, variantPresentation.currentStock]);

    const handleMobileEditClick = useCallback(() => {
        if (!product) return;
        if (currentProductCartItem) {
            router.push(`/constructor?productId=${currentProductCartItem.product_id}&editCartItemId=${encodeURIComponent(currentProductCartItem.id)}`);
            return;
        }
        router.push(`/constructor?productId=${product.id}`);
    }, [currentProductCartItem, product, router]);

    const handleMobileBuyClick = useCallback(() => {
        if (items.length > 0) router.push('/checkout');
    }, [items.length, router]);

    const handleWaitlistSubmit = useCallback((event: FormEvent) => {
        event.preventDefault();
        setTimeout(() => {
            setWaitlistSent(true);
            setTimeout(() => {
                setShowWaitlistForm(false);
                setWaitlistSent(false);
                setWaitlistData(EMPTY_WAITLIST_DATA);
            }, 3000);
        }, 800);
    }, []);

    const updateWaitlistField = useCallback((field: keyof WaitlistData, value: string) => {
        setWaitlistData(current => ({ ...current, [field]: value }));
    }, []);

    return {
        product,
        loadedImagesCount,
        setLoadedImagesCount,
        selectedColor,
        setSelectedColor,
        selectedSize,
        setSelectedSize,
        showSizeChart,
        setShowSizeChart,
        relatedSlideIndex,
        setRelatedSlideIndex,
        activeDesktopImg,
        showWaitlistForm,
        setShowWaitlistForm,
        waitlistSent,
        waitlistData,
        updateWaitlistField,
        hasScrolled,
        currentProductCartItem,
        currentCartColor,
        normalizedProductDescription,
        reviewImagesToRender,
        nextProducts,
        relatedProductPages,
        addProductToCart,
        handleProductBack,
        handleMobileAddClick,
        handleMobileEditClick,
        handleMobileBuyClick,
        handleWaitlistSubmit,
        ...variantPresentation,
    };
};

export type ProductPageViewModel = ReturnType<typeof useProductPage>;
