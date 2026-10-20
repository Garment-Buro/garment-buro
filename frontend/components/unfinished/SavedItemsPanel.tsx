"use client";

import type { CSSProperties } from "react";
import Image from "next/image";

import type { UnfinishedSurfaceViewModel } from "@/hooks/unfinished/useUnfinishedSurface";
import { DRAFTS_PANEL_BACKGROUND } from "@/lib/unfinished/config/ui";
import type { ProjectSummary } from '@/lib/projects/types';
import styles from "./UnfinishedSurface.module.css";

type SavedItemsPanelProps = {
    surface: UnfinishedSurfaceViewModel;
};

type SavedItemCardProps = {
    item: ProjectSummary;
    isActive: boolean;
    variant: "draft" | "collection";
    onSelect: (item: ProjectSummary) => void;
};

function SavedItemCard({ item, isActive, variant, onSelect }: SavedItemCardProps) {
    return (
        <article className={`${styles.draftItem} ${isActive ? styles.activeDraftItem : ""}`} role="listitem">
            <button
                className={`${styles.surfaceButton} ${styles.draftPreview}`}
                type="button"
                onClick={() => onSelect(item)}
                aria-label={`${variant === 'collection' ? 'Изделие' : 'Черновик'} ${String(item.id).padStart(3, '0')}`}
            >
                <div className={styles.productImageWrap}>
                    <span className={styles.projectCardPlaceholder}>#{item.id}</span>
                    {variant === "draft" && (
                        <Image src="/unfinished_card_edit.svg" alt="" width={24} height={24} className={styles.draftEditIcon} />
                    )}
                </div>
                <div className={styles.draftMeta}>
                    <span className={styles.draftNumber}>{String(item.id).padStart(3, '0')}</span>
                    <span className={styles.draftName}>{item.title}</span>
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
                    {surface.projectLibrary.account.userId !== null && surface.projectLibrary.status === 'ready' && (
                        <button type="button" className={styles.projectLibraryAction}
                            onClick={() => void surface.projectLibrary.retry()}>Обновить список проектов</button>
                    )}
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
                    {surface.projectLibrary.nextCursor !== null && (
                        <button type="button" className={styles.profilePrimaryButton}
                            disabled={surface.projectLibrary.loadingMore}
                            onClick={() => void surface.projectLibrary.loadMore()}>
                            {surface.projectLibrary.loadingMore ? 'ЗАГРУЖАЕМ…' : 'ПОКАЗАТЬ ЕЩЁ'}
                        </button>
                    )}
                    {Boolean(surface.projectLibrary.error) && surface.projectLibrary.status === 'ready' && (
                        <p role="alert">Не удалось загрузить следующую страницу. Повторите загрузку.</p>
                    )}
                </div>
            </div>
        </div>
    );
}
