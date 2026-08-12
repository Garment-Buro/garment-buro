import { usePathname } from 'next/navigation';
import {
    useCallback,
    useEffect,
    useLayoutEffect,
    useRef,
    useState,
    type MouseEvent,
} from 'react';

import { CATEGORY_MENU_FADE_OUT_MS } from '@/lib/navigation/data';
import type { CategoryMenuItem, ElevatedButtonRect } from '@/lib/navigation/types';

const useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;

type UseAdaptiveHeaderBehaviorOptions = {
    isConstructor: boolean;
    elevateSizeButton: boolean;
    label: string;
    resolvedTopOffset: number;
    title: string;
    subtitle: string;
};

export const useAdaptiveHeaderBehavior = ({
    isConstructor,
    elevateSizeButton,
    label,
    resolvedTopOffset,
    title,
    subtitle,
}: UseAdaptiveHeaderBehaviorOptions) => {
    const pathname = usePathname();
    const headerRef = useRef<HTMLElement>(null);
    const categoryMenuRef = useRef<HTMLElement>(null);
    const previousPathnameRef = useRef(pathname);
    const sizeButtonRef = useRef<HTMLButtonElement>(null);
    const [elevatedButtonRect, setElevatedButtonRect] = useState<ElevatedButtonRect | null>(null);
    const [categoryMenuTop, setCategoryMenuTop] = useState<number | null>(null);
    const [isCategoryMenuOpen, setIsCategoryMenuOpen] = useState(false);
    const [isCategoryMenuMounted, setIsCategoryMenuMounted] = useState(false);
    const [expandedCategoryId, setExpandedCategoryId] = useState<CategoryMenuItem['id'] | null>(null);
    const categoryMenuCloseTimerRef = useRef<number | null>(null);
    const categoryMenuOpenFrameRef = useRef<number | null>(null);

    const closeCategoryMenu = useCallback(() => {
        setIsCategoryMenuOpen(false);
        setExpandedCategoryId(null);
        if (categoryMenuOpenFrameRef.current !== null) {
            window.cancelAnimationFrame(categoryMenuOpenFrameRef.current);
            categoryMenuOpenFrameRef.current = null;
        }
        if (categoryMenuCloseTimerRef.current !== null) window.clearTimeout(categoryMenuCloseTimerRef.current);
        categoryMenuCloseTimerRef.current = window.setTimeout(() => {
            setIsCategoryMenuMounted(false);
            categoryMenuCloseTimerRef.current = null;
        }, CATEGORY_MENU_FADE_OUT_MS);
    }, []);

    const openCategoryMenu = useCallback(() => {
        if (categoryMenuCloseTimerRef.current !== null) {
            window.clearTimeout(categoryMenuCloseTimerRef.current);
            categoryMenuCloseTimerRef.current = null;
        }
        const headerRect = headerRef.current?.getBoundingClientRect();
        if (headerRect) setCategoryMenuTop(headerRect.bottom + 8);
        setIsCategoryMenuMounted(true);
        categoryMenuOpenFrameRef.current = window.requestAnimationFrame(() => {
            categoryMenuOpenFrameRef.current = window.requestAnimationFrame(() => {
                setIsCategoryMenuOpen(true);
                categoryMenuOpenFrameRef.current = null;
            });
        });
    }, []);

    useEffect(() => () => {
        if (categoryMenuOpenFrameRef.current !== null) window.cancelAnimationFrame(categoryMenuOpenFrameRef.current);
        if (categoryMenuCloseTimerRef.current !== null) window.clearTimeout(categoryMenuCloseTimerRef.current);
    }, []);

    useEffect(() => {
        if (previousPathnameRef.current === pathname) return;
        previousPathnameRef.current = pathname;
        const animationFrameId = window.requestAnimationFrame(closeCategoryMenu);
        return () => window.cancelAnimationFrame(animationFrameId);
    }, [closeCategoryMenu, pathname]);

    useEffect(() => {
        if (!isCategoryMenuOpen) return;
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') closeCategoryMenu();
        };
        const handlePointerDown = (event: PointerEvent) => {
            const target = event.target;
            if (!(target instanceof Node)) return;
            if (headerRef.current?.contains(target) || categoryMenuRef.current?.contains(target)) return;
            closeCategoryMenu();
        };
        window.addEventListener('keydown', handleKeyDown);
        document.addEventListener('pointerdown', handlePointerDown, true);
        return () => {
            window.removeEventListener('keydown', handleKeyDown);
            document.removeEventListener('pointerdown', handlePointerDown, true);
        };
    }, [closeCategoryMenu, isCategoryMenuOpen]);

    useIsomorphicLayoutEffect(() => {
        if (!isCategoryMenuOpen || isConstructor) return;
        const updateCategoryMenuTop = () => {
            const rect = headerRef.current?.getBoundingClientRect();
            if (rect) setCategoryMenuTop(rect.bottom + 8);
        };
        updateCategoryMenuTop();
        window.addEventListener('resize', updateCategoryMenuTop);
        window.addEventListener('orientationchange', updateCategoryMenuTop);
        window.visualViewport?.addEventListener('resize', updateCategoryMenuTop);
        return () => {
            window.removeEventListener('resize', updateCategoryMenuTop);
            window.removeEventListener('orientationchange', updateCategoryMenuTop);
            window.visualViewport?.removeEventListener('resize', updateCategoryMenuTop);
        };
    }, [isCategoryMenuOpen, isConstructor, resolvedTopOffset, title, subtitle]);

    useIsomorphicLayoutEffect(() => {
        if (!isConstructor || !elevateSizeButton) {
            setElevatedButtonRect(null);
            return;
        }
        const updateElevatedButtonRect = () => {
            const rect = sizeButtonRef.current?.getBoundingClientRect();
            if (rect) setElevatedButtonRect({ top: rect.top, left: rect.left, width: rect.width });
        };
        updateElevatedButtonRect();
        window.addEventListener('resize', updateElevatedButtonRect);
        window.addEventListener('orientationchange', updateElevatedButtonRect);
        window.visualViewport?.addEventListener('resize', updateElevatedButtonRect);
        return () => {
            window.removeEventListener('resize', updateElevatedButtonRect);
            window.removeEventListener('orientationchange', updateElevatedButtonRect);
            window.visualViewport?.removeEventListener('resize', updateElevatedButtonRect);
        };
    }, [isConstructor, elevateSizeButton, label]);

    const toggleCategory = (categoryId: CategoryMenuItem['id']) => {
        setExpandedCategoryId(current => current === categoryId ? null : categoryId);
    };
    const handleMenuClickCapture = (event: MouseEvent<HTMLElement>) => {
        const target = event.target as HTMLElement;
        if (target.closest('a')) closeCategoryMenu();
    };

    return {
        headerRef,
        categoryMenuRef,
        sizeButtonRef,
        elevatedButtonRect,
        categoryMenuTop,
        isCategoryMenuOpen,
        isCategoryMenuMounted,
        expandedCategoryId,
        closeCategoryMenu,
        openCategoryMenu,
        toggleCategory,
        handleMenuClickCapture,
    };
};

