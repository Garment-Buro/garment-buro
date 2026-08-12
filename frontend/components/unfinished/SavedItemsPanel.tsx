"use client";

import type { CSSProperties } from "react";
import Image from "next/image";

import type { UnfinishedSurfaceViewModel } from "@/hooks/unfinished/useUnfinishedSurface";
import { DRAFTS_PANEL_BACKGROUND } from "@/lib/unfinished/config/ui";
import type { SavedProfileItem } from "@/lib/unfinished/utils/savedItems";
import { ConstructorDraftPreview } from "@/components/unfinished/ConstructorDraftPreview";
import styles from "./UnfinishedSurface.module.css";

type SavedItemsPanelProps = {
    surface: UnfinishedSurfaceViewModel;
};

type SavedItemCardProps = {
    item: SavedProfileItem;
    isActive: boolean;
    variant: "draft" | "collection";
    onSelect: (item: SavedProfileItem) => void;
};

function SavedItemCard({ item, isActive, variant, onSelect }: SavedItemCardProps) {
    return (
        <article className={`${styles.draftItem} ${isActive ? styles.activeDraftItem : ""}`} role="listitem">
            <button
                className={`${styles.surfaceButton} ${styles.draftPreview}`}
                type="button"
                onClick={() => onSelect(item)}
                aria-label={variant === "collection" ? `Изделие ${item.number}` : `Черновик ${item.number}`}
            >
                <div className={styles.productImageWrap}>
                    {variant === "draft" ? (
                        <ConstructorDraftPreview item={item} className={styles.productImage} />
                    ) : (
                        <Image src={item.imageSrc} alt="" width={110} height={100} className={styles.productImage} />
                    )}
                    {variant === "draft" && (
                        <Image src="/unfinished_card_edit.svg" alt="" width={24} height={24} className={styles.draftEditIcon} />
                    )}
                </div>
                <div className={styles.draftMeta}>
                    <span className={styles.draftNumber}>{item.number}</span>
                    <span className={styles.draftName}>{item.name}</span>
                </div>
            </button>
        </article>
    );
}

export function SavedItemsPanel({ surface }: SavedItemsPanelProps) {
    const variant = surface.isCollectionTab ? "collection" : "draft";

    return (
        <div className={styles.draftsShell}>
            <div className={styles.panelRail} aria-hidden="true">
                <Image src="/numbers.svg" alt="" width={7} height={82} className={styles.panelNumbers} />
                <div className={styles.leftScrollbar}>
                    <div className={styles.leftScrollbarTrack} />
                    <div
                        className={styles.scrollThumb}
                        style={{ "--scroll-progress": surface.scrollProgress } as CSSProperties}
                    />
                </div>
            </div>

            <div className={styles.draftsPhotoPanel} style={{ backgroundImage: DRAFTS_PANEL_BACKGROUND }}>
                <div
                    className={`${styles.expandedDraftsSurface} ${surface.isBottomBarExpanded ? styles.expandedDraftsSurfaceActive : ""}`}
                    aria-hidden="true"
                />
                <div
                    className={`${styles.paperBackground} ${surface.isBottomBarExpanded ? styles.paperBackgroundActive : ""}`}
                    aria-hidden="true"
                >
                    <Image src="/paper1.webp" alt="" width={650} height={236} />
                    <Image src="/paper2.webp" alt="" width={649} height={373} />
                    <Image src="/paper3.webp" alt="" width={649} height={427} />
                </div>

                <div className={styles.draftsViewport} onScroll={surface.handleScroll}>
                    <div className={styles.draftsGrid} role="list">
                        {surface.gridItems.map((item) => (
                            <SavedItemCard
                                key={item.id}
                                item={item}
                                isActive={surface.selectedItem?.id === item.id}
                                variant={variant}
                                onSelect={surface.handleSelectGridItem}
                            />
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
