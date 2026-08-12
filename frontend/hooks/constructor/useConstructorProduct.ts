"use client";

import { useCallback, useEffect, useState } from "react";

import { getProduct } from "@/lib/api/products";
import type { GarmentFit } from "@/lib/constructor/types";
import {
    createDefaultFit,
    getFirstAvailableSize,
    getProductDimensions,
} from "@/lib/constructor/utils/constructor";
import type { ProductData } from "@/lib/products/types";

export const useConstructorProduct = (productId: string | null) => {
    const [product, setProduct] = useState<ProductData | null>(null);
    const [selectedSize, setSelectedSize] = useState("");
    const [selectedFit, setSelectedFit] = useState<GarmentFit | null>(null);
    const [isSizeModalOpen, setIsSizeModalOpen] = useState(false);

    useEffect(() => {
        if (!productId) return;
        const controller = new AbortController();

        getProduct(productId, controller.signal)
            .then((data) => {
                setProduct(data);
                const firstSize = getFirstAvailableSize(data);
                setSelectedSize((current) => current || firstSize);
                setSelectedFit((current) => current || createDefaultFit(
                    firstSize,
                    getProductDimensions(data, firstSize),
                ));
            })
            .catch((error) => {
                if (error instanceof DOMException && error.name === "AbortError") return;
                console.warn("Constructor product loading failed:", error);
            });

        return () => controller.abort();
    }, [productId]);

    const handleSaveFit = useCallback((fit: GarmentFit) => {
        setSelectedSize(fit.selectedSize);
        setSelectedFit(fit);
        setIsSizeModalOpen(false);
    }, []);

    return {
        product,
        selectedSize,
        setSelectedSize,
        selectedFit,
        setSelectedFit,
        isSizeModalOpen,
        setIsSizeModalOpen,
        handleSaveFit,
    };
};
