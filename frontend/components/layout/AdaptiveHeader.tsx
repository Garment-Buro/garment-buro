"use client";

import React, { useEffect, useRef } from "react";
import NextLink from "next/link";
import { createPortal } from "react-dom";
import { AppIcon } from "@/components/icons/AppIcon";
import { useAdaptiveHeaderBehavior } from "@/hooks/navigation/useAdaptiveHeaderBehavior";
import { CATEGORY_MENU_ITEMS } from "@/lib/navigation/data";
import type { AdaptiveHeaderProps } from "@/lib/navigation/types";
import styles from "./AdaptiveHeader.module.css";

const CATEGORY_MENU_GLASS_STYLE: React.CSSProperties = {
    backdropFilter: "blur(12px) saturate(160%)",
    WebkitBackdropFilter: "blur(12px) saturate(160%)",
    background: "rgb(227 227 227 / 85%)",
    border: "1px solid rgba(255, 255, 255, 0.3)",
    boxShadow: "rgba(0, 0, 0, 0.1) 0px 8px 32px, rgba(255, 255, 255, 0.5) 0px 1px 2px inset, rgba(255, 255, 255, 0.05) 0px -1px 2px inset",
    overflow: "hidden",
};

const BrandContent = ({ title, subtitle }: { title: string; subtitle: string }) => {
    const videoRef = useRef<HTMLVideoElement>(null);

    useEffect(() => {
        const video = videoRef.current;
        if (!video) return;

        video.muted = true;
        video.play().catch(() => {});
    }, []);

    return (
        <>
            <span className={styles.logo} aria-hidden="true">
                <video
                    ref={videoRef}
                    src="/logo_anim.mp4"
                    autoPlay
                    muted
                    loop
                    playsInline
                    controls={false}
                    disablePictureInPicture
                    controlsList="nodownload nofullscreen noremoteplayback"
                    preload="auto"
                    className={styles.logoVideo}
                    onLoadedMetadata={(event) => {
                        event.currentTarget.muted = true;
                        event.currentTarget.play().catch(() => {});
                    }}
                />
            </span>
            <span className={styles.brandText}>
                <span className={styles.title}>{title}</span>
                <span className={styles.subtitle}>{subtitle}</span>
            </span>
        </>
    );
};

export const AdaptiveHeader = ({
    variant = "catalog",
    withBackdrop = false,
    fixed = true,
    topOffset,
    title = "Garment Buro",
    subtitle = "my collection",
    logoHref = "/",
    onLogoClick,
    onMenuClick,
    sizeLabel,
    onSizeClick,
    elevateSizeButton = false,
    className = "",
}: AdaptiveHeaderProps) => {
    const isConstructor = variant === "constructor";
    const resolvedTopOffset = topOffset ?? (isConstructor ? 0 : 20);
    const label = sizeLabel || "Размер: XXL";
    const {
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
    } = useAdaptiveHeaderBehavior({
        isConstructor,
        elevateSizeButton,
        label,
        resolvedTopOffset,
        title,
        subtitle,
    });
    const headerClassName = [
        styles.header,
        fixed ? styles.fixed : styles.notFixed,
        isConstructor ? styles.constructor : styles.catalog,
        className,
    ].filter(Boolean).join(" ");
    const style = { "--header-top-offset": `${resolvedTopOffset}px` } as React.CSSProperties;
    const categoryMenuStyle = {
        ...style,
        ...CATEGORY_MENU_GLASS_STYLE,
        ...(categoryMenuTop == null ? {} : { "--category-menu-top": `${categoryMenuTop}px` }),
    } as React.CSSProperties;
    const brand = onLogoClick ? (
        <button
            type="button"
            className={styles.brandButton}
            onClick={() => {
                closeCategoryMenu();
                onLogoClick();
            }}
            aria-label="На главную"
        >
            <BrandContent title={title} subtitle={subtitle} />
        </button>
    ) : (
        <NextLink href={logoHref} className={styles.brandLink} aria-label="На главную" onClick={closeCategoryMenu}>
            <BrandContent title={title} subtitle={subtitle} />
        </NextLink>
    );

    const renderSizeButton = ({
        elevated = false,
        hidden = false,
    }: {
        elevated?: boolean;
        hidden?: boolean;
    } = {}) => (
        <button
            ref={elevated ? undefined : sizeButtonRef}
            type="button"
            className={[styles.sizeButton, elevated ? styles.sizeButtonElevated : ""].filter(Boolean).join(" ")}
            onClick={onSizeClick}
            style={elevated && elevatedButtonRect ? {
                top: elevatedButtonRect.top,
                left: elevatedButtonRect.left,
                width: elevatedButtonRect.width,
            } : hidden ? { visibility: "hidden" } : undefined}
            aria-hidden={hidden ? true : undefined}
            tabIndex={hidden ? -1 : undefined}
        >
            <span>{label}</span>
            <AppIcon name="size-filter" width={15} height={11} className={styles.sizeIcon} />
        </button>
    );
    const sizeButton = renderSizeButton({ hidden: isConstructor && elevateSizeButton && Boolean(elevatedButtonRect) });
    const elevatedSizeButton = elevatedButtonRect ? renderSizeButton({ elevated: true }) : null;

    const handleMenuButtonClick = () => {
        onMenuClick?.();

        if (isConstructor) return;
        if (isCategoryMenuOpen) {
            closeCategoryMenu();
        } else {
            openCategoryMenu();
        }
    };

    const handleMenuSelection = () => {
        closeCategoryMenu();
    };

    const categoryMenu = !isConstructor && isCategoryMenuMounted ? (
        <nav
            ref={categoryMenuRef}
            id="adaptive-category-menu"
            className={`${styles.categoryMenu} ${isCategoryMenuOpen ? styles.categoryMenuVisible : styles.categoryMenuHidden}`}
            style={categoryMenuStyle}
            aria-label="Категории"
            onClickCapture={handleMenuClickCapture}
        >
            {CATEGORY_MENU_ITEMS.map((category, index) => {
                const isExpanded = expandedCategoryId === category.id;

                return (
                    <React.Fragment key={category.id}>
                        {index > 0 && <div className={styles.categoryDivider} aria-hidden="true" />}
                        <div
                            className={[styles.categoryItem, isExpanded ? styles.categoryItemExpanded : ""].filter(Boolean).join(" ")}
                        >
                            <button
                                type="button"
                                className={styles.categoryTitle}
                                onClick={() => toggleCategory(category.id)}
                                aria-expanded={isExpanded}
                            >
                                {category.title}
                            </button>
                            <span className={styles.categoryContentSlot}>
                                <button
                                    type="button"
                                    className={styles.categorySubtitle}
                                    onClick={() => toggleCategory(category.id)}
                                    aria-hidden={isExpanded ? true : undefined}
                                    tabIndex={isExpanded ? -1 : undefined}
                                >
                                    {category.subtitle}
                                </button>
                                <span
                                    className={styles.categoryExpandedGrid}
                                    aria-label={`${category.title}: категории`}
                                    aria-hidden={isExpanded ? undefined : true}
                                >
                                    {category.items.map((item) => (
                                        <button
                                            key={item}
                                            type="button"
                                            className={styles.categoryLinkLabel}
                                            data-menu-selection
                                            onClick={handleMenuSelection}
                                        >
                                            {item}
                                        </button>
                                    ))}
                                </span>
                            </span>
                        </div>
                    </React.Fragment>
                );
            })}
            <div className={styles.categoryDivider} aria-hidden="true" />
            <NextLink
                href="/light-running"
                className={styles.lightRunningLink}
                onClick={closeCategoryMenu}
            >
                Light running
            </NextLink>
        </nav>
    ) : null;
    const categoryMenuPortal = !isConstructor && categoryMenu && typeof document !== "undefined"
        ? createPortal(categoryMenu, document.body)
        : categoryMenu;

    return (
        <>
            {withBackdrop && (
                <div
                    className={[styles.backdrop, fixed ? "" : styles.backdropInline].filter(Boolean).join(" ")}
                    aria-hidden="true"
                    data-adaptive-header-backdrop
                />
            )}
            <header ref={headerRef} className={headerClassName} style={style}>
                {brand}

                {isConstructor ? (
                    sizeButton
                ) : (
                    <button
                        type="button"
                        className={styles.burgerButton}
                        onClick={handleMenuButtonClick}
                        aria-label={isCategoryMenuOpen ? "Закрыть меню" : "Открыть меню"}
                        aria-expanded={isCategoryMenuOpen}
                        aria-controls="adaptive-category-menu"
                    >
                        <span className={styles.burgerIcon} aria-hidden="true">
                            <span className={styles.burgerLine} />
                            <span className={styles.burgerLine} />
                            <span className={styles.burgerLine} />
                        </span>
                    </button>
                )}
            </header>
            {categoryMenuPortal}
            {isConstructor && elevateSizeButton && elevatedSizeButton && typeof document !== "undefined"
                ? createPortal(elevatedSizeButton, document.body)
                : null}
        </>
    );
};
