"use client";

import Image from "next/image";

import { AppIcon } from "@/components/icons/AppIcon";
import { ProfilePanel } from "@/components/unfinished/ProfilePanel";
import { SavedItemsPanel } from "@/components/unfinished/SavedItemsPanel";
import { ConstructorDraftPreview } from "@/components/unfinished/ConstructorDraftPreview";
import { UnfinishedDeletePopup } from "@/components/shared/ConstructorFlowPopup";
import { useUnfinishedSurface } from "@/hooks/unfinished/useUnfinishedSurface";
import { COLLECTION_HERO_IMAGE, navigationItems } from "@/lib/unfinished/config/ui";
import type { ProfileTab } from "@/lib/unfinished/types";
import styles from "./UnfinishedSurface.module.css";

type UnfinishedSurfaceProps = {
    isOverlay?: boolean;
    onClose?: () => void;
    initialTab?: ProfileTab;
};

export function UnfinishedSurface({ isOverlay = false, onClose, initialTab = "unfinished" }: UnfinishedSurfaceProps) {
    const surface = useUnfinishedSurface({ isOverlay, onClose, initialTab });
    const {
        activeTab,
        selectedDraft,
        selectedCollectionItem,
        selectedItem,
        bottomPanelState,
        setBottomPanelState,
        isTabContentVisible,
        isClosing,
        isDeleteConfirmOpen,
        setIsDeleteConfirmOpen,
        isUnfinishedTab,
        isCollectionTab,
        isProfileTab,
        isBottomBarCollapsed,
        isBottomBarExpanded,
        isExpandedOnlyProfilePanel,
        activeTitle,
        activeEmptyCopy,
        sectionBackgroundLayers,
        pageLabel,
        handleContentAction,
        handleDeleteSelectedItem,
        confirmDeleteSelectedItem,
        handleBack,
        handleToggleBottomPanel,
        handleCollapsedPanelTouchStart,
        handleCollapsedPanelTouchEnd,
        handleCollapsedPanelTouchCancel,
        handlePanelStepTouchStart,
        handlePanelStepTouchEnd,
        handlePanelStepTouchCancel,
        handleSelectTab,
    } = surface;
    const bottomPanelStateClass = {
        collapsed: styles.collapsedBottomBarSection,
        normal: styles.normalBottomBarSection,
        expanded: styles.expandedBottomBarSection,
    }[bottomPanelState];

    return (
        <>
            <UnfinishedDeletePopup
                isOpen={isDeleteConfirmOpen}
                onClose={() => setIsDeleteConfirmOpen(false)}
                onConfirm={confirmDeleteSelectedItem}
            />
            <main
                className={`${styles.page} ${isOverlay ? styles.overlayPage : ""} ${isClosing ? styles.pageClosing : ""}`}
                aria-label={pageLabel}
            >
                <section
                    className={`${styles.unfinishedSection} ${isClosing ? styles.unfinishedSectionClosing : ""} ${isCollectionTab ? styles.collectionSection : ""} ${isProfileTab ? styles.profileSection : ""} ${bottomPanelStateClass} ${!isTabContentVisible ? styles.tabLayoutSwitching : ""}`}
                >
                    <div className={styles.sectionBackground} aria-hidden="true">
                        {sectionBackgroundLayers.map((background) => (
                            <div
                                key={background.id}
                                className={`${styles.sectionBackgroundLayer} ${background.active ? styles.sectionBackgroundLayerActive : ""}`}
                                style={{ backgroundImage: `url('${background.src}')` }}
                            />
                        ))}
                    </div>
                    <div className={`${styles.tabContent} ${isTabContentVisible ? "" : styles.tabContentHidden}`}>
                        <div className={styles.controlBlock}>
                            <button
                                className={`${styles.surfaceButton} ${styles.backButton}`}
                                type="button"
                                aria-label="Назад"
                                onClick={handleBack}
                            >
                                {isUnfinishedTab ? (
                                    <AppIcon name="back" width={22} height={19} className="text-white" />
                                ) : (
                                    <Image src="/back_icon_item.svg" alt="" width={22} height={19} />
                                )}
                            </button>

                            {isUnfinishedTab && selectedDraft && (
                                <button
                                    className={`${styles.surfaceButton} ${styles.deleteButton}`}
                                    type="button"
                                    aria-label="Удалить черновик"
                                    onClick={handleDeleteSelectedItem}
                                >
                                    <AppIcon name="delete" width={16} height={18} className="text-[#BE2222]" />
                                </button>
                            )}
                        </div>

                        {!isProfileTab && (
                            <div className={styles.collectionInfoBlock}>
                                <h1 className={styles.pageTitle}>{activeTitle}</h1>
                                {selectedItem && (
                                    <div className={styles.collectionHeaderMeta}>
                                        <span>{selectedItem.number}</span>
                                        <span>{selectedItem.name}</span>
                                    </div>
                                )}
                            </div>
                        )}

                        {isProfileTab && <h1 className={styles.pageTitle}>{activeTitle}</h1>}

                        {!isProfileTab && isTabContentVisible && (
                            <div className={styles.contentPanel}>
                                <div
                                    className={styles.selectedProductFrame}
                                    key={`${activeTab}-${selectedItem?.id ?? "empty"}`}
                                >
                                    {selectedDraft && isUnfinishedTab && (
                                        <ConstructorDraftPreview
                                            item={selectedDraft}
                                            className={styles.selectedProductImage}
                                            priority
                                        />
                                    )}

                                    {isCollectionTab && selectedCollectionItem && (
                                        <Image
                                            src={COLLECTION_HERO_IMAGE}
                                            alt=""
                                            width={288}
                                            height={395}
                                            className={styles.collectionProductImage}
                                            priority
                                        />
                                    )}

                                    {selectedDraft && isUnfinishedTab && (
                                        <button
                                            className={`${styles.surfaceButton} ${styles.contentAction} ${styles.selectedContentAction}`}
                                            type="button"
                                            onClick={handleContentAction}
                                        >
                                            <Image
                                                src="/unfinished_card_edit.svg"
                                                alt=""
                                                width={32}
                                                height={32}
                                                className={styles.emptyMark}
                                            />
                                            <span>Продолжить</span>
                                        </button>
                                    )}

                                    {!selectedItem && (
                                        <button
                                            className={`${styles.surfaceButton} ${styles.contentAction} ${styles.emptyContentAction} ${isCollectionTab ? styles.collectionEmptyContentAction : ""}`}
                                            type="button"
                                            onClick={handleContentAction}
                                        >
                                            <span className={styles.emptyStateTitle}>{activeEmptyCopy.title}</span>
                                            <span className={styles.emptyStateText}>{activeEmptyCopy.text}</span>
                                            {activeEmptyCopy.cta && <span className={styles.emptyStateCta}>{activeEmptyCopy.cta}</span>}
                                        </button>
                                    )}
                                </div>
                            </div>
                        )}

                        <div className={`${styles.bottomPanel} ${isProfileTab ? styles.profileBottomPanel : ""}`}>
                            <div className={styles.bottomPanelTitle}>ВЕРА САМСОНОВА</div>

                            <div
                                className={`${styles.bottomPanelFrame} ${isProfileTab ? styles.profileBottomPanelFrame : ""} ${isBottomBarCollapsed ? styles.collapsedBottomPanelFrame : ""}`}
                                onTouchStart={handleCollapsedPanelTouchStart}
                                onTouchEnd={handleCollapsedPanelTouchEnd}
                                onTouchCancel={handleCollapsedPanelTouchCancel}
                            >
                                <div
                                    className={styles.panelTopShadow}
                                    onTouchStart={handlePanelStepTouchStart}
                                    onTouchEnd={handlePanelStepTouchEnd}
                                    onTouchCancel={handlePanelStepTouchCancel}
                                />

                                {isBottomBarCollapsed && (
                                    <div className={styles.collapsedPanelHeader}>{activeTitle}</div>
                                )}

                                {bottomPanelState === "normal" && !isExpandedOnlyProfilePanel && (
                                    <button
                                        className={`${styles.surfaceButton} ${styles.panelExpandButton}`}
                                        type="button"
                                        aria-label="Развернуть панель полностью"
                                        onClick={() => setBottomPanelState("expanded")}
                                    >
                                        <AppIcon name="expand" width={8} height={8} className="text-[#868686]" />
                                    </button>
                                )}

                                <button
                                    className={`${styles.surfaceButton} ${styles.panelToggleButton} ${!isBottomBarCollapsed ? styles.panelToggleButtonDown : ""}`}
                                    type="button"
                                    aria-expanded={!isBottomBarCollapsed}
                                    aria-label={isBottomBarCollapsed ? "Показать нижнюю панель" : isExpandedOnlyProfilePanel ? "Скрыть нижнюю панель" : isBottomBarExpanded ? "Вернуть обычный размер панели" : "Скрыть нижнюю панель"}
                                    onClick={handleToggleBottomPanel}
                                >
                                    <AppIcon name="chevron-up" width={7} height={7} className="text-[#454545]" />
                                </button>

                                <div className={`${styles.bottomPanelInner} ${isProfileTab ? styles.profileBottomPanelInner : ""}`}>
                                    {isProfileTab ? <ProfilePanel surface={surface} /> : <SavedItemsPanel surface={surface} />}
                                </div>
                            </div>
                        </div>
                    </div>

                    <nav className={styles.profileNav} aria-label="Разделы профиля">
                        {navigationItems.flatMap((item, index) => [
                            index > 0 ? (
                                <span key={`divider-${item.label}`} className={styles.navDivider} aria-hidden="true" />
                            ) : null,
                            <button
                                key={`button-${item.label}`}
                                className={`${styles.surfaceButton} ${styles.navButton} ${activeTab === item.id ? styles.activeNavButton : ""}`}
                                type="button"
                                onClick={() => handleSelectTab(item)}
                            >
                                {item.label}
                            </button>,
                        ])}
                    </nav>
                </section>
            </main>
        </>
    );
}
