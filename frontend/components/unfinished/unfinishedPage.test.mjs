import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const appRoot = path.resolve(process.cwd(), "app");
const componentsRoot = path.resolve(process.cwd(), "components");
const pagePath = path.join(appRoot, "unfinished", "page.tsx");
const lkPagePath = path.join(appRoot, "lk", "page.tsx");
const stylesPath = path.join(componentsRoot, "unfinished", "UnfinishedSurface.module.css");
const surfacePath = path.join(componentsRoot, "unfinished", "UnfinishedSurface.tsx");
const profilePanelPath = path.join(componentsRoot, "unfinished", "ProfilePanel.tsx");
const savedItemsPanelPath = path.join(componentsRoot, "unfinished", "SavedItemsPanel.tsx");
const draftPreviewPath = path.join(componentsRoot, "unfinished", "ConstructorDraftPreview.tsx");
const draftPreviewStylesPath = path.join(componentsRoot, "unfinished", "ConstructorDraftPreview.module.css");
const unfinishedConfigPath = path.join(process.cwd(), "lib", "unfinished", "config", "ui.ts");
const unfinishedSavedItemFixturesPath = path.join(process.cwd(), "lib", "unfinished", "fixtures", "savedItems.ts");
const unfinishedProfileFixturesPath = path.join(process.cwd(), "lib", "unfinished", "fixtures", "profile.ts");
const unfinishedTypesPath = path.join(process.cwd(), "lib", "unfinished", "types.ts");
const unfinishedUtilsPath = path.join(process.cwd(), "lib", "unfinished", "utils", "unfinished.ts");
const unfinishedHookPath = path.join(process.cwd(), "hooks", "unfinished", "useUnfinishedSurface.ts");
const savedItemsPath = path.join(process.cwd(), "lib", "unfinished", "utils", "savedItems.ts");
const overlayPagePath = path.join(appRoot, "@modal", "(.)unfinished", "page.tsx");
const readUnfinishedSource = () => [
    surfacePath,
    profilePanelPath,
    savedItemsPanelPath,
    unfinishedHookPath,
    unfinishedConfigPath,
    unfinishedSavedItemFixturesPath,
    unfinishedProfileFixturesPath,
    unfinishedTypesPath,
    unfinishedUtilsPath,
]
    .map(file => fs.readFileSync(file, "utf8"))
    .join("\n");

test("unfinished page route defines the mobile drafts surface", () => {
    assert.equal(fs.existsSync(pagePath), true);
    assert.equal(fs.existsSync(stylesPath), true);
    assert.equal(fs.existsSync(overlayPagePath), true);

    const pageSource = readUnfinishedSource();
    const stylesSource = fs.readFileSync(stylesPath, "utf8");

    assert.match(pageSource, /className=\{`\$\{styles\.unfinishedSection\}/);
    assert.match(pageSource, /sectionBackgroundLayers\.map\(\(background\) =>/);
    assert.match(pageSource, /styles\.sectionBackgroundLayerActive/);
    assert.doesNotMatch(pageSource, /className=\{`\$\{styles\.tabContent\}[\s\S]{0,180}backgroundImage/);
    assert.equal((pageSource.match(/className=\{`\$\{styles\.unfinishedSection\}/g) ?? []).length, 1);
    assert.match(pageSource, /unfinished_content_bg\.webp/);
    assert.match(pageSource, /my_collection_bg\.webp/);
    assert.match(pageSource, /profile_bg\.webp/);
    assert.match(pageSource, /name="back"/);
    assert.match(pageSource, /back_icon_item\.svg/);
    assert.match(pageSource, /name="delete"/);
    assert.match(pageSource, /window\.location\.replace\("\/\?selectForConstructor=1"\)/);
    assert.match(pageSource, /router\.push\(`\/constructor\?productId=\$\{selectedDraft\.productId\}&draftId=\$\{encodeURIComponent\(selectedDraft\.id\)\}`\)/);
    assert.match(pageSource, /loadSavedProfileItems\(CONSTRUCTOR_DRAFTS_STORAGE_KEY\)/);
    assert.match(pageSource, /loadSavedProfileItems\(MY_COLLECTION_STORAGE_KEY\)/);
    assert.match(pageSource, /Продолжить/);
    assert.match(pageSource, /UNFINISHED/);
    assert.match(pageSource, /MY COLLECTION/);
    assert.match(pageSource, /PROFILE/);
    assert.match(pageSource, /COLLAPSED_PANEL_SWIPE_UP_THRESHOLD_PX = 36/);
    assert.match(pageSource, /PANEL_STEP_SWIPE_THRESHOLD_PX = 36/);
    assert.match(pageSource, /PANEL_TOGGLE_CLICK_SUPPRESSION_MS = 450/);
    assert.match(pageSource, /TouchEvent<HTMLDivElement>/);
    assert.match(pageSource, /onTouchStart={handleCollapsedPanelTouchStart}/);
    assert.match(pageSource, /onTouchEnd={handleCollapsedPanelTouchEnd}/);
    assert.match(pageSource, /onTouchStart={handlePanelStepTouchStart}/);
    assert.match(pageSource, /onTouchEnd={handlePanelStepTouchEnd}/);
    assert.doesNotMatch(pageSource, /onTouchMove=|onWheel=/);

    assert.match(stylesSource, /\.overlayPage\s*\{[^}]*background:\s*rgba\(0,\s*0,\s*0,\s*0\.5\)/s);
    assert.match(stylesSource, /\.overlayPage\s*\{[^}]*z-index:\s*2147483646/s);
    assert.match(stylesSource, /\.overlayPage\s*\{[^}]*animation:\s*unfinished-overlay-in 0\.42s ease both/s);
    assert.match(stylesSource, /@keyframes unfinished-overlay-in\s*\{[\s\S]*?rgba\(0,\s*0,\s*0,\s*0\)[\s\S]*?rgba\(0,\s*0,\s*0,\s*0\.5\)/s);
    assert.match(stylesSource, /\.overlayPage\.pageClosing\s*\{[^}]*animation:\s*unfinished-overlay-out 0\.42s ease both/s);
    assert.match(stylesSource, /--unfinished-section-height:\s*clamp\(720px,\s*194\.595vw,\s*1245px\)/);
    assert.match(stylesSource, /\.unfinishedSection\s*\{[^}]*bottom:\s*0[^}]*width:\s*100%/s);
    assert.match(stylesSource, /\.page\s*\{[^}]*position:\s*fixed[^}]*height:\s*100dvh[^}]*min-height:\s*-webkit-fill-available/s);
    assert.match(stylesSource, /--unfinished-visible-height:\s*min\([\s\S]*?var\(--unfinished-section-height\)[\s\S]*?100dvh - max\(20px, env\(safe-area-inset-top\)\)/);
    assert.match(stylesSource, /height:\s*var\(--unfinished-visible-height\)/);
    assert.match(stylesSource, /border-radius:\s*20px 20px 0 0/);
    assert.match(stylesSource, /border:\s*2px solid rgba\(247,\s*247,\s*247,\s*0\.63\)/);
    assert.match(stylesSource, /\.controlBlock\s*\{[^}]*padding:\s*20px[^}]*pointer-events:\s*none/s);
    assert.match(stylesSource, /\.controlBlock \.surfaceButton\s*\{[^}]*pointer-events:\s*auto/s);
    assert.match(stylesSource, /\.bottomPanel\s*\{[^}]*bottom:\s*calc\(var\(--unfinished-nav-height\) \+ var\(--unfinished-safe-bottom\)\)[^}]*padding:\s*0 clamp\(5px,\s*1\.351vw,\s*9px\)/s);
    assert.match(stylesSource, /\.bottomPanelFrame\s*\{[^}]*border:\s*1px solid rgb\(217,\s*217,\s*217\)[^}]*background:\s*rgb\(243,\s*243,\s*243\)/s);
    assert.match(stylesSource, /\.bottomPanelFrame\s*\{[^}]*border-radius:\s*8px/s);
    assert.doesNotMatch(stylesSource, /\.bottomPanelFrame\s*\{[^}]*border-radius:\s*8px 8px 0 0/s);
    assert.match(stylesSource, /\.collapsedBottomPanelFrame\s*\{[^}]*touch-action:\s*none/s);
    assert.match(stylesSource, /\.contentPanel\s*\{[^}]*top:\s*var\(--unfinished-content-top\)[^}]*var\(--unfinished-content-bottom-height\)/s);
    assert.match(stylesSource, /\.selectedProductImage,\s*\.collectionProductImage\s*\{[^}]*width:\s*clamp\(288px,\s*77\.838vw,\s*498px\)[^}]*height:\s*clamp\(395px,\s*106\.757vw,\s*683px\)[^}]*max-width:\s*calc\(100% - clamp\(24px,\s*6\.486vw,\s*42px\)\)[^}]*var\(--unfinished-content-bottom-height\)[^}]*object-fit:\s*contain[^}]*max-height 0\.5s cubic-bezier\(0\.22,\s*1,\s*0\.36,\s*1\)[^}]*transform 0\.5s cubic-bezier\(0\.22,\s*1,\s*0\.36,\s*1\)/s);
    assert.match(stylesSource, /\.unfinishedSection:not\(\.collectionSection\)\.collapsedBottomBarSection \.selectedProductImage\s*\{[^}]*transform:\s*translateZ\(0\) scale\(1\.32\)/s);
    assert.match(stylesSource, /\.collectionHeaderMeta span:last-child\s*\{[^}]*max-width:\s*min\(30vw,\s*230px\)/s);
    assert.match(stylesSource, /\.navButton\s*\{[^}]*color:\s*#BBBBBB/s);
    assert.match(stylesSource, /\.activeNavButton\s*\{[^}]*color:\s*#5E5C5C/s);
    assert.match(pageSource, /Math\.min\(1,\s*Math\.max\(0,\s*scrollTop \/ scrollableHeight\)\)/);
    assert.match(stylesSource, /animation:\s*unfinished-sheet-in 0\.58s/);
    assert.match(stylesSource, /\.unfinishedSectionClosing\s*\{[^}]*animation:\s*unfinished-sheet-out 0\.42s/s);
    assert.match(pageSource, /UNFINISHED_SHEET_EXIT_MS = 420/);
    assert.match(pageSource, /setIsClosing\(true\)[\s\S]*window\.setTimeout\([\s\S]*router\.back\(\)/);
});

test("unfinished draft preview layers saved decorations over a centered garment", () => {
    assert.equal(fs.existsSync(draftPreviewPath), true);
    assert.equal(fs.existsSync(draftPreviewStylesPath), true);

    const pageSource = readUnfinishedSource();
    const previewSource = fs.readFileSync(draftPreviewPath, "utf8");
    const previewStylesSource = fs.readFileSync(draftPreviewStylesPath, "utf8");
    const stylesSource = fs.readFileSync(stylesPath, "utf8");

    assert.match(pageSource, /<ConstructorDraftPreview[\s\S]*item=\{item\}/);
    assert.match(pageSource, /<ConstructorDraftPreview[\s\S]*item=\{selectedDraft\}/);
    assert.match(previewSource, /data-constructor-draft-preview="true"/);
    assert.match(previewSource, /customization\.decorations\.filter/);
    assert.match(previewSource, /data-constructor-draft-decoration=\{decoration\.variantId\}/);
    assert.match(previewStylesSource, /\.canvas\s*\{[^}]*position:\s*absolute[^}]*left:\s*50%[^}]*top:\s*50%[^}]*translate\(-50%, -50%\)/s);
    assert.match(stylesSource, /\.selectedProductFrame\s*>\s*\.selectedProductImage\[data-constructor-draft-preview="true"\]\s*\{[^}]*overflow:\s*visible/s);
    assert.match(stylesSource, /\.selectedProductImage\[data-constructor-draft-preview="true"\]\s*\{[^}]*max-width:\s*75%[^}]*max-height:\s*75%/s);
});

test("unfinished panel assets are available", () => {
    const assetNames = [
        "back_icon_item.svg",
        "landing_1.webp",
        "unfinished_content_bg.webp",
        "unfinished_bg_2.webp",
        "unfinished_bg_3.webp",
        "my_collection_bg.webp",
        "my_collection_template.webp",
        "numbers.svg",
        "unfinished_card_edit.svg",
        "paper1.webp",
        "paper2.webp",
        "paper3.webp",
    ];

    for (const assetName of assetNames) {
        assert.equal(fs.existsSync(path.resolve(process.cwd(), "public", assetName)), true);
    }
});

test("unfinished and collection share responsive Figma tray states", () => {
    const pageSource = readUnfinishedSource();
    const stylesSource = fs.readFileSync(stylesPath, "utf8");

    assert.match(pageSource, /const isUnfinishedTab = activeTab === "unfinished"/);
    assert.match(pageSource, /isCollectionTab \? styles\.collectionSection : ""/);
    assert.match(pageSource, /useState<BottomPanelState>\("collapsed"\)/);
    assert.doesNotMatch(pageSource, /initialTab === "profile" \? "expanded" : "collapsed"/);
    assert.match(pageSource, /const nextBottomPanelState: BottomPanelState = "collapsed"/);
    assert.match(pageSource, /setBottomPanelState\(nextBottomPanelState\)/);
    assert.match(pageSource, /onClick=\{\(\) => setBottomPanelState\("expanded"\)\}/);
    assert.match(pageSource, /if \(currentState === "collapsed"\) return getCollapsedPanelOpenState\(isProfileTab, activeProfileTab\)/);
    assert.match(pageSource, /if \(currentState === "expanded"\) return isExpandedOnlyProfilePanel \? "collapsed" : "normal"/);
    assert.match(pageSource, /onClick=\{handleToggleBottomPanel\}/);
    assert.match(pageSource, /currentState === "expanded" \? "normal" : "collapsed"/);
    assert.match(pageSource, /export const getPanelStepState[\s\S]*deltaY > 0[\s\S]*: "expanded"/);
    assert.match(pageSource, /setBottomPanelState\(nextState\)/);

    assert.match(stylesSource, /--unfinished-nav-height:\s*clamp\(72px,\s*20vw,\s*78px\)/);
    assert.match(stylesSource, /--unfinished-bottom-normal-height:\s*clamp\(195px,\s*52\.703vw,\s*337px\)/);
    assert.match(stylesSource, /--unfinished-bottom-expanded-height:\s*min\([\s\S]*?clamp\(520px,\s*142\.43vw,\s*912px\)/);
    assert.match(stylesSource, /--unfinished-bottom-collapsed-height:\s*35px/);
    assert.match(stylesSource, /\.expandedBottomBarSection\s*\{[^}]*--unfinished-bottom-height:\s*var\(--unfinished-bottom-expanded-height\)/s);
    assert.match(stylesSource, /\.normalBottomBarSection\s*\{[^}]*--unfinished-bottom-height:\s*var\(--unfinished-bottom-normal-height\)/s);
    assert.match(stylesSource, /\.collapsedBottomBarSection\s*\{[^}]*--unfinished-bottom-height:\s*var\(--unfinished-bottom-collapsed-height\)/s);
    assert.match(stylesSource, /\.contentPanel\s*\{[^}]*display:\s*flex/s);
    assert.match(stylesSource, /\.selectedProductFrame\s*\{[^}]*position:\s*relative/s);
    assert.match(pageSource, /!isProfileTab\s*&&\s*\(\s*<div className=\{styles\.collectionInfoBlock\}>[\s\S]*?<h1 className=\{styles\.pageTitle\}>\{activeTitle\}<\/h1>[\s\S]*?selectedItem\.number[\s\S]*?selectedItem\.name/s);
    assert.match(stylesSource, /--draft-card-width:\s*clamp\(110px,\s*29\.73vw,\s*190px\)/);
    assert.match(stylesSource, /--draft-photo-height:\s*clamp\(100px,\s*27\.03vw,\s*173px\)/);
    assert.match(stylesSource, /--draft-card-height:\s*calc\(var\(--draft-photo-height\) \+ 30px\)/);
    assert.match(stylesSource, /\.draftsGrid\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*var\(--draft-card-width\)\)[^}]*column-gap:\s*clamp\(35px,\s*9\.46vw,\s*61px\)[^}]*row-gap:\s*clamp\(20px,\s*5\.41vw,\s*35px\)/s);
    assert.match(stylesSource, /\.expandedBottomBarSection \.panelNumbers\s*\{[^}]*top:\s*clamp\(20px,\s*5\.405vw,\s*35px\)/s);
    assert.match(stylesSource, /\.surfaceButton:focus\s*\{[^}]*outline:\s*none/s);
    assert.match(stylesSource, /\.surfaceButton:focus-visible\s*\{[^}]*outline:\s*none/s);
    assert.doesNotMatch(stylesSource, /\.surfaceButton:focus-visible\s*\{[^}]*outline-offset/s);
});

test("PWA keeps profile navigation above the bottom safe area", () => {
    const stylesSource = fs.readFileSync(stylesPath, "utf8");

    assert.match(stylesSource, /--unfinished-safe-bottom:\s*0px/);
    assert.match(stylesSource, /:global\(html\[data-browser-surface="pwa"\]\) \.unfinishedSection\s*\{[^}]*--unfinished-safe-bottom:\s*env\(safe-area-inset-bottom\)/s);
    assert.match(stylesSource, /@media \(display-mode: standalone\)\s*\{[\s\S]*?\.unfinishedSection\s*\{[^}]*--unfinished-safe-bottom:\s*env\(safe-area-inset-bottom\)/s);
    assert.match(stylesSource, /\.profileNav\s*\{[^}]*bottom:\s*calc\(clamp\(20px,\s*5\.41vw,\s*26px\) \+ var\(--unfinished-safe-bottom\)\)/s);
    assert.match(stylesSource, /--unfinished-bottom-expanded-height:\s*min\([\s\S]*?var\(--unfinished-visible-height\)[\s\S]*?var\(--unfinished-safe-bottom\)/);
});

test("collection selection preserves the current tray state", () => {
    const pageSource = readUnfinishedSource();
    const collectionSelectionHandler = pageSource.match(/const handleSelectGridItem = \(item: SavedProfileItem\) => \{[\s\S]*?\n    \};/)?.[0] ?? "";
    const collectionSelectionBranch = collectionSelectionHandler.match(/if \(activeTab === "my-collection"\) \{[\s\S]*?return;\n        \}/)?.[0] ?? "";

    assert.match(collectionSelectionBranch, /setSelectedCollectionId\(item\.id\)/);
    assert.doesNotMatch(collectionSelectionBranch, /setBottomPanelState/);
});

test("unfinished and collection use the approved three-state content bar", () => {
    const pageSource = readUnfinishedSource();
    const stylesSource = fs.readFileSync(stylesPath, "utf8");

    assert.match(pageSource, /type BottomPanelState = "collapsed" \| "normal" \| "expanded"/);
    assert.match(pageSource, /useState<BottomPanelState>/);
    assert.match(pageSource, /name="chevron-up"/);
    assert.match(pageSource, /name="expand"/);
    assert.match(pageSource, /numbers\.svg/);
    assert.match(pageSource, /unfinished_card_edit\.svg/);
    assert.match(pageSource, /paper1\.webp/);
    assert.match(pageSource, /paper2\.webp/);
    assert.match(pageSource, /paper3\.webp/);
    assert.match(pageSource, /back_icon_item\.svg/);

    assert.match(stylesSource, /--unfinished-bottom-normal-height:\s*clamp\(195px,\s*52\.703vw,\s*337px\)/);
    assert.match(stylesSource, /--unfinished-bottom-collapsed-height:\s*35px/);
    assert.match(stylesSource, /transition:\s*height 0\.5s cubic-bezier\(0\.22,\s*1,\s*0\.36,\s*1\)/);
    assert.match(stylesSource, /\.expandedBottomBarSection\s*\{[^}]*--unfinished-content-bottom-height:\s*var\(--unfinished-bottom-normal-height\)/s);
    assert.match(stylesSource, /\.unfinishedSection\.expandedBottomBarSection:not\(\.profileSection\)\s*\{[^}]*--unfinished-bottom-height:\s*calc\(var\(--unfinished-bottom-expanded-height\)/s);
    assert.match(stylesSource, /\.panelTopShadow\s*\{[^}]*height:\s*10px[^}]*opacity:\s*0\.4[^}]*touch-action:\s*none/s);
    assert.match(stylesSource, /\.panelToggleButton\s*\{[^}]*width:\s*30px[^}]*height:\s*30px/s);
    assert.match(stylesSource, /\.panelToggleButton img\s*\{[^}]*top:\s*10px[^}]*right:\s*10px[^}]*width:\s*7px[^}]*height:\s*7px/s);
    assert.match(stylesSource, /\.panelExpandButton\s*\{[^}]*right:\s*29px[^}]*width:\s*32px[^}]*height:\s*30px/s);
    assert.match(stylesSource, /\.panelExpandButton img\s*\{[^}]*width:\s*8px[^}]*height:\s*8px/s);
    assert.match(stylesSource, /\.draftMeta\s*\{[^}]*gap:\s*2px/s);
    assert.match(stylesSource, /\.productImageWrap\s*\{[^}]*background:\s*transparent/s);
    assert.match(stylesSource, /\.activeDraftItem \.productImageWrap\s*\{[^}]*background:\s*rgba\(255,\s*255,\s*255,\s*0\.54\)/s);
    assert.match(stylesSource, /\.paperBackground\s*\{[^}]*opacity:\s*0/s);
    assert.match(stylesSource, /\.paperBackgroundActive\s*\{[^}]*opacity:\s*0\.4/s);
    assert.match(stylesSource, /\.paperBackground img\s*\{[^}]*display:\s*block[^}]*width:\s*100%/s);
    assert.match(stylesSource, /\.draftsPhotoPanel\s*\{[^}]*background-repeat:\s*no-repeat/s);
    assert.match(stylesSource, /\.expandedDraftsSurface\s*\{[^}]*background-color:\s*#F3F3F3[^}]*opacity:\s*0/s);
    assert.match(stylesSource, /\.expandedDraftsSurfaceActive\s*\{[^}]*opacity:\s*1/s);
    assert.match(pageSource, /className=\{styles\.draftsPhotoPanel\}/);
    assert.match(pageSource, /styles\.expandedDraftsSurfaceActive/);
    assert.match(pageSource, /styles\.paperBackgroundActive/);
    assert.match(stylesSource, /\.collectionInfoBlock\s*\{[^}]*top:\s*clamp\(64px,\s*17\.297vw,\s*111px\)/s);
    assert.match(stylesSource, /\.contentPanel\s*\{[^}]*transition:\s*bottom 0\.5s cubic-bezier/s);
    assert.match(stylesSource, /\.tabContent\s*\{[^}]*transition:\s*opacity 0\.2s ease/s);
    assert.match(stylesSource, /\.tabContentHidden\s*\{[^}]*opacity:\s*0/s);
    assert.match(stylesSource, /\.sectionBackground\s*\{[^}]*z-index:\s*0[^}]*pointer-events:\s*none/s);
    assert.match(stylesSource, /\.sectionBackgroundLayer\s*\{[^}]*opacity:\s*0[^}]*background-repeat:\s*no-repeat[^}]*transition:\s*opacity 0\.42s ease/s);
    assert.match(stylesSource, /\.sectionBackgroundLayerActive\s*\{[^}]*opacity:\s*1/s);
    assert.match(pageSource, /TAB_FADE_OUT_MS = 220/);
    assert.match(pageSource, /SECTION_BACKGROUND_IMAGES\.forEach\(\(?src\)? => \{\s*const image = new window\.Image\(\)/s);
    assert.match(pageSource, /setIsTabContentVisible\(false\)/);
    assert.match(pageSource, /const ENABLE_UNFINISHED_PANEL_BACKGROUND_SWITCH = false/);
    assert.match(pageSource, /src:\s*"\/landing_1\.webp",\s*active:\s*isUnfinishedTab/);
    assert.match(pageSource, /src:\s*"\/unfinished_bg_2\.webp",\s*active:\s*isUnfinishedTab && bottomPanelState === "normal"/);
    assert.match(pageSource, /src:\s*"\/unfinished_bg_3\.webp",\s*active:\s*isUnfinishedTab && isBottomBarExpanded/);
    assert.match(pageSource, /DRAFTS_PANEL_BACKGROUND = "url\('\/unfinished_bg\.webp'\)"/);
    assert.match(pageSource, /export const COLLECTION_PREVIEW_FIXTURES: SavedProfileItem\[\]/);
    assert.match(pageSource, /const collectionFixtures = fixturesEnabled \? COLLECTION_PREVIEW_FIXTURES : EMPTY_SAVED_ITEMS/);
    assert.match(pageSource, /collectionFixtures\[0\]\?\.id/);
    assert.match(pageSource, /!isTabContentVisible \? styles\.tabLayoutSwitching : ""/);
    assert.match(pageSource, /!isProfileTab && isTabContentVisible && \(/);
    assert.match(pageSource, /key=\{`\$\{activeTab\}-\$\{selectedItem\?\.id \?\? "empty"\}`\}/);
    assert.match(pageSource, /selectedDraft && isUnfinishedTab/);
    assert.doesNotMatch(pageSource, /selectedDraft && !isCollectionTab/);
    assert.match(stylesSource, /\.unfinishedSection\.tabLayoutSwitching,[\s\S]*?\.tabLayoutSwitching \.contentPanel,[\s\S]*?\.tabLayoutSwitching \.collectionProductImage\s*\{[^}]*transition:\s*none/s);
    assert.match(stylesSource, /\.tabLayoutSwitching \.sectionBackgroundLayer/);
    assert.match(pageSource, /requestAnimationFrame\(\(\) => \{\s*tabFadeInFrameRef\.current = window\.requestAnimationFrame\(\(\) => \{\s*setIsTabContentVisible\(true\)/s);
});

test("profile route renders the mobile profile surface", () => {
    assert.equal(fs.existsSync(lkPagePath), true);

    const lkPageSource = fs.readFileSync(lkPagePath, "utf8");
    const pageSource = readUnfinishedSource();
    const stylesSource = fs.readFileSync(stylesPath, "utf8");

    assert.match(lkPageSource, /<UnfinishedSurface\s+initialTab="profile"\s+\/>/);
    assert.match(pageSource, /initialTab\?:\s*ProfileTab/);
    assert.match(pageSource, /useState<ProfileTab>\(initialTab\)/);
    assert.match(pageSource, /useState<BottomPanelState>\("collapsed"\)/);
    assert.match(pageSource, /profile_bg\.webp/);
    assert.match(pageSource, /discount_bg\.webp/);
    assert.match(pageSource, /discount_header_icon\.svg/);
    assert.match(pageSource, /name="discount-lock"/);
    assert.match(pageSource, /ЗАКАЗЫ/);
    assert.match(pageSource, /ПОДДЕРЖКА/);
    assert.match(pageSource, /НАСТРОЙКИ/);
    assert.match(pageSource, /Скидка на первый заказ/);
    assert.match(pageSource, /Заказ подтверждён/);
    assert.match(pageSource, /Получен/);
    assert.match(pageSource, /ЛИЧНАЯ ИНФОРМАЦИЯ/);
    assert.match(pageSource, /ПОЛУЧИТЬ КОД/);
    assert.match(pageSource, /ОТПРАВИТЬ/);
    assert.match(pageSource, /Удалить аккаунт/);
    assert.match(pageSource, /width=\{28\}[\s\S]{0,80}height=\{20\}[\s\S]{0,100}styles\.profileDiscountIcon/);
    assert.match(pageSource, /const isExpandedOnlyProfileTab = \(tab: ProfilePanelTab\) => tab === "support" \|\| tab === "settings"/);
    assert.match(pageSource, /setBottomPanelState\(isExpandedOnlyProfileTab\(nextProfileTab\) \? "expanded" : "normal"\)/);
    assert.match(pageSource, /const handleToggleOrder = \(orderId: string\) => \{[\s\S]*?setExpandedOrderId\(shouldCollapseOrder \? null : orderId\)[\s\S]*?setBottomPanelState\(shouldCollapseOrder \? "normal" : "expanded"\)/s);
    assert.match(pageSource, /if \(isExpandedOrderPanel && isBottomBarExpanded\) \{[\s\S]*?setExpandedOrderId\(null\)[\s\S]*?setBottomPanelState\("normal"\)/s);
    assert.match(pageSource, /function OrderSummary[\s\S]*?onClick=\{\(\) => onToggle\(order\.id\)\}/s);
    assert.match(pageSource, /function ExpandedOrder[\s\S]*?onClick=\{onCollapse\}/s);
    const normalOrdersBranch = pageSource.match(/function ProfileOrders[\s\S]*?function ProfileDiscounts/)?.[0] ?? "";
    assert.match(normalOrdersBranch, /styles\.orderSummaries/);
    assert.doesNotMatch(normalOrdersBranch, /OrderStatusList|styles\.orderTimeline/);
    assert.match(stylesSource, /\.profileBottomPanel\s*\{/);
    assert.match(stylesSource, /\.profileBottomPanelFrame\s*\{[^}]*background-color:\s*#F3F3F3[^}]*background-image:\s*url\('\/unfinished_bg\.webp'\)[^}]*background-repeat:\s*no-repeat/s);
    assert.match(stylesSource, /\.profileBottomPanelInner\s*\{[^}]*background:\s*transparent/s);
    assert.match(stylesSource, /\.profileTopTabs\s*\{[^}]*display:\s*flex[^}]*gap:\s*20px[^}]*padding:\s*0 45px 0 20px/s);
    assert.match(stylesSource, /\.profileSection \.panelToggleButton,\s*\.profileSection \.panelExpandButton\s*\{[^}]*display:\s*flex[^}]*height:\s*32px[^}]*align-items:\s*center[^}]*justify-content:\s*center/s);
    assert.match(stylesSource, /\.profileSection \.panelToggleButton img,\s*\.profileSection \.panelExpandButton img\s*\{[^}]*position:\s*static/s);
    assert.match(stylesSource, /\.profileSection \.panelExpandButton img\s*\{[^}]*transform:\s*translateX\(5px\)/s);
    assert.match(stylesSource, /\.profileTopTab\s*\{[^}]*color:\s*#393939[^}]*font-family:\s*Manrope[^}]*font-size:\s*12px[^}]*font-style:\s*normal[^}]*font-weight:\s*600[^}]*line-height:\s*normal/s);
    assert.match(stylesSource, /\.profileTopTabActive\s*\{[^}]*color:\s*#393939/s);
    assert.match(stylesSource, /\.profileDiscountIcon\s*\{[^}]*width:\s*28px[^}]*height:\s*20px[^}]*opacity:\s*0\.5/s);
    assert.match(stylesSource, /\.profileOrdersListCard\s*\{[^}]*padding:\s*8px 20px 16px/s);
    assert.match(stylesSource, /\.discountCard\s*\{/);
    assert.match(stylesSource, /\.profileSettingsCard[\s\S]{0,80}\{/);
    assert.match(stylesSource, /\.profileSection \.pageTitle\s*\{[^}]*top:\s*clamp\(58px,\s*15\.676vw,\s*100px\)/s);
});

test("profile settings fields and confirmation code are editable", () => {
    const pageSource = readUnfinishedSource();
    const stylesSource = fs.readFileSync(stylesPath, "utf8");

    assert.doesNotMatch(pageSource, /readOnly/);
    assert.match(pageSource, /value=\{surface\.loginEmail\}[\s\S]{0,160}surface\.setLoginEmail\(event\.target\.value\)/);
    assert.match(pageSource, /surface\.profileCode\.map\(\(character, index\) =>/);
    assert.match(pageSource, /inputMode="numeric"/);
    assert.match(pageSource, /surface\.handleProfileCodeChange\(index, event\.target\.value\)/);
    assert.match(pageSource, /value=\{surface\.profileName\}[\s\S]{0,160}surface\.setProfileName/);
    assert.match(pageSource, /value=\{surface\.profilePhone\}[\s\S]{0,160}surface\.setProfilePhone/);
    assert.match(pageSource, /value=\{surface\.profileEmail\}[\s\S]{0,160}surface\.setProfileEmail/);
    assert.match(stylesSource, /\.profileCodeSlots input\s*\{/);
});

test("profile uses the same inner panel controls as collection and unfinished", () => {
    const pageSource = readUnfinishedSource();
    const stylesSource = fs.readFileSync(stylesPath, "utf8");

    assert.match(pageSource, /isProfileTab \? <ProfilePanel surface=\{surface\} \/> : <SavedItemsPanel surface=\{surface\} \/>/);
    assert.match(pageSource, /profileBottomPanel/);
    assert.match(pageSource, /profileBottomPanelInner/);
    assert.match(pageSource, /export function ProfilePanel[\s\S]*profileTopTabs[\s\S]*<ProfileContent surface=\{surface\} \/>/);
    assert.doesNotMatch(pageSource, /!\s*isProfileTab\s*&&\s*\(\s*<div className=\{styles\.bottomPanel\}/);
    assert.doesNotMatch(pageSource, /isProfileTab\s*\?\s*\(\s*<div className=\{styles\.profilePanel\}/);
    assert.equal((pageSource.match(/styles\.panelToggleButton(?=[}\s])/g) ?? []).length, 1);
    assert.equal((pageSource.match(/styles\.panelExpandButton/g) ?? []).length, 1);

    assert.match(stylesSource, /\.profileBottomPanel\s*\{/);
    assert.match(stylesSource, /\.profileBottomPanelInner\s*\{/);
    assert.doesNotMatch(stylesSource, /\.profilePanel\s*\{/);
});

test("unfinished page has local saved-item storage helpers", () => {
    assert.equal(fs.existsSync(savedItemsPath), true);

    const savedItemsSource = fs.readFileSync(savedItemsPath, "utf8");

    assert.match(savedItemsSource, /CONSTRUCTOR_DRAFTS_STORAGE_KEY = ['"]plus2opacity-constructor-drafts['"]/);
    assert.match(savedItemsSource, /MY_COLLECTION_STORAGE_KEY = ['"]plus2opacity-my-collection['"]/);
    assert.match(savedItemsSource, /buildSavedProfileItem/);
    assert.match(savedItemsSource, /loadSavedProfileItems/);
    assert.match(savedItemsSource, /saveConstructorDraft/);
});

test("unfinished route hides global chrome around the mobile surface", () => {
    const pageChromePath = path.join(process.cwd(), "lib", "browser", "utils", "pageChrome.ts");
    const chromeFileGroups = [
        [path.join(componentsRoot, "layout", "Header.tsx"), pageChromePath],
        [path.join(componentsRoot, "layout", "Footer.tsx"), pageChromePath],
        [path.join(componentsRoot, "shared", "AnimatedLogo.tsx")],
        [
            path.join(componentsRoot, "shared", "SplashScreen.tsx"),
            path.join(process.cwd(), "hooks", "browser", "useSplashController.ts"),
            path.join(process.cwd(), "lib", "browser", "utils", "splash.ts"),
        ],
        [
            path.join(componentsRoot, "shared", "CookieConsent.tsx"),
            path.join(process.cwd(), "hooks", "browser", "useCookieConsent.ts"),
            path.join(process.cwd(), "lib", "browser", "utils", "cookieConsent.ts"),
        ],
    ];

    for (const chromeFiles of chromeFileGroups) {
        const source = chromeFiles.map(file => fs.readFileSync(file, "utf8")).join("\n");
        assert.match(source, /['"]\/unfinished['"]/);
        assert.match(source, /['"]\/lk['"]/);
    }
});
