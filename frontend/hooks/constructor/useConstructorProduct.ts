"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";

import { getConstructorProduct } from "@/lib/api/storefront";
import type { GarmentFit } from "@/lib/constructor/types";
import {
  createDefaultFit,
  getProductDimensions,
} from "@/lib/constructor/utils/constructor";
import { ConstructorProductResource } from "@/lib/constructor/productResource";
import { constructorSelectionStock, initialConstructorSelection, restoreConstructorSelection } from '@/lib/constructor/selection';

type Selection = { key: string | null; size: string; color: string | null; fit: GarmentFit | null };

export const useConstructorProduct = (productId: string | null) => {
  const [resource] = useState(() => new ConstructorProductResource());
  const snapshot = useSyncExternalStore(
    resource.subscribe,
    resource.getSnapshot,
    resource.getSnapshot,
  );
  // A render for a different ID happens before its load effect. Hide old data now.
  const product = snapshot.key === productId ? snapshot.product : null;
  const error = snapshot.key === productId ? snapshot.error : null;
  const [selection, setSelection] = useState<Selection>({
    key: null,
    size: "",
    color: null,
    fit: null,
  });
  const defaultSelection = useMemo<Selection>(() => {
    const initial = initialConstructorSelection(product);
    const size = initial.size;
    return {
      key: productId,
      size,
      color: initial.color,
      fit: product
        ? createDefaultFit(size, getProductDimensions(product, size, initial.color))
        : null,
    };
  }, [product, productId]);
  const selectedSize = product
    ? selection.key === productId
      ? selection.size
      : defaultSelection.size
    : "";
  const selectedFit = product
    ? selection.key === productId
      ? selection.fit
      : defaultSelection.fit
    : null;
  const selectedColor = product
    ? selection.key === productId ? selection.color : defaultSelection.color
    : null;
  const selectionAvailable = constructorSelectionStock(product, { size: selectedSize, color: selectedColor }) > 0;
  const [isSizeModalOpen, setIsSizeModalOpen] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    void resource.load(productId, getConstructorProduct);
    return () => resource.dispose();
  }, [productId, attempt, resource]);

  const restoreSelection = useCallback(
    (size: string, fit: GarmentFit, color?: string | null) => {
      if (!product) return;
      setSelection({ key: productId, ...restoreConstructorSelection(product, size, color), fit });
    },
    [product, productId],
  );

  const handleSaveFit = useCallback(
    (fit: GarmentFit, color: string | null) => {
      if (!constructorSelectionStock(product, { size: fit.selectedSize, color })) return;
      setSelection({ key: productId, size: fit.selectedSize, color, fit });
      setIsSizeModalOpen(false);
    },
    [product, productId],
  );

  return {
    product,
    error,
    retry: () => setAttempt((value) => value + 1),
    selectedSize,
    selectedColor,
    selectionAvailable,
    restoreSelection,
    selectedFit,
    isSizeModalOpen,
    setIsSizeModalOpen,
    handleSaveFit,
  };
};
