import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const constructorSource = [
    path.join(root, "components", "constructor", "ConstructorPage.tsx"),
    path.join(root, "components", "constructor", "ConstructorWorkspace.tsx"),
    path.join(root, "components", "constructor", "ConstructorInstructionOverlay.tsx"),
    path.join(root, "components", "constructor", "DecorationOptionCard.tsx"),
    path.join(root, "components", "constructor", "FitSlider.tsx"),
    path.join(root, "components", "constructor", "RotateModelIcon.tsx"),
    path.join(root, "components", "constructor", "SizeFitModal.tsx"),
    path.join(root, "lib", "constructor", "constants.ts"),
    path.join(root, "lib", "constructor", "types.ts"),
    path.join(root, "lib", "constructor", "utils", "constructor.ts"),
    path.join(root, "lib", "api", "products.ts"),
    path.join(root, "hooks", "constructor", "useConstructorPageEnvironment.ts"),
    path.join(root, "hooks", "constructor", "useConstructorProduct.ts"),
    path.join(root, "hooks", "constructor", "useConstructorDerivedState.ts"),
    path.join(root, "hooks", "constructor", "useConstructorPageController.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const landingSource = [
    path.join(root, "components", "shared", "LandingPage.tsx"),
    path.join(root, "hooks", "catalog", "useCatalogPage.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const unfinishedSource = [
    path.join(root, "components", "unfinished", "UnfinishedSurface.tsx"),
    path.join(root, "components", "unfinished", "ProfilePanel.tsx"),
    path.join(root, "components", "unfinished", "SavedItemsPanel.tsx"),
    path.join(root, "hooks", "unfinished", "useUnfinishedSurface.ts"),
    path.join(root, "lib", "unfinished", "config", "ui.ts"),
    path.join(root, "lib", "unfinished", "fixtures", "savedItems.ts"),
    path.join(root, "lib", "unfinished", "fixtures", "profile.ts"),
    path.join(root, "lib", "unfinished", "types.ts"),
    path.join(root, "lib", "unfinished", "utils", "unfinished.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const popupSource = fs.readFileSync(path.join(root, "components", "shared", "ConstructorFlowPopup.tsx"), "utf8");
const popupBaseSource = fs.readFileSync(path.join(root, "components", "shared", "Popup.tsx"), "utf8");
const productCardSource = [
    path.join(root, "components", "shared", "ProductCard.tsx"),
    path.join(root, "hooks", "catalog", "useDesktopCatalogCardVideo.ts"),
    path.join(root, "hooks", "cart", "useCatalogCartItem.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const mobileProductCardSource = [
    path.join(root, "components", "shared", "MobileProductCard.tsx"),
    path.join(root, "hooks", "catalog", "useMobileCatalogCardVideo.ts"),
    path.join(root, "hooks", "cart", "useCatalogCartItem.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const unfinishedStylesSource = fs.readFileSync(path.join(root, "components", "unfinished", "UnfinishedSurface.module.css"), "utf8");
const canvasSource = [
    path.join(root, "components", "constructor", "KonvaCanvas.tsx"),
    path.join(root, "hooks", "constructor", "useKonvaCanvasController.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const layoutSource = [
    path.join(root, "app", "layout.tsx"),
    path.join(root, "lib", "browser", "utils", "splash.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const globalStylesSource = fs.readFileSync(path.join(root, "app", "globals.css"), "utf8");
const constructorRouteSource = fs.readFileSync(path.join(root, "app", "[constructorRoute]", "page.tsx"), "utf8");
const appEnvironmentSource = [
    path.join(root, "providers", "AppEnvironmentProvider.tsx"),
    path.join(root, "lib", "browser", "utils", "pageChrome.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const adaptiveHeaderSource = [
    path.join(root, "components", "layout", "AdaptiveHeader.tsx"),
    path.join(root, "hooks", "navigation", "useAdaptiveHeaderBehavior.ts"),
    path.join(root, "lib", "navigation", "data.ts"),
    path.join(root, "lib", "navigation", "types.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const adaptiveHeaderStylesSource = fs.readFileSync(path.join(root, "components", "layout", "AdaptiveHeader.module.css"), "utf8");
const lkPageSource = fs.readFileSync(path.join(root, "app", "lk", "page.tsx"), "utf8");
const loginPageSource = fs.readFileSync(path.join(root, "app", "login", "page.tsx"), "utf8");
const splashSource = [
    path.join(root, "components", "shared", "SplashScreen.tsx"),
    path.join(root, "hooks", "browser", "useSplashController.ts"),
    path.join(root, "providers", "SplashBoundary.tsx"),
    path.join(root, "lib", "browser", "utils", "splash.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const offerSource = fs.readFileSync(path.join(root, "app", "offer", "page.tsx"), "utf8");
const cartStoreSource = [
    path.join(root, "store", "cartStore.ts"),
    path.join(root, "lib", "cart", "types.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const cartPresentationSource = fs.readFileSync(path.join(root, "lib", "cart", "utils", "cartAction.ts"), "utf8");
const checkoutSource = [
    path.join(root, "app", "checkout", "page.tsx"),
    path.join(root, "components", "checkout", "CheckoutOrderSummary.tsx"),
    path.join(root, "lib", "checkout", "utils", "checkout.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const orderContentSource = [
    path.join(root, "components", "shared", "OrderContent.tsx"),
    path.join(root, "lib", "orders", "utils", "orderDetails.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const savedItemsSource = fs.readFileSync(path.join(root, "lib", "unfinished", "utils", "savedItems.ts"), "utf8");
const unfinishedOverlayRouteSource = fs.readFileSync(path.join(root, "app", "@modal", "(.)unfinished", "page.tsx"), "utf8");
const modalCatchAllSource = fs.readFileSync(path.join(root, "app", "@modal", "[...catchAll]", "page.tsx"), "utf8");
const defaultDecorationsSource = [
    path.join(root, "lib", "constructor", "config", "defaultDecorations.ts"),
    path.join(root, "lib", "constructor", "utils", "data.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");

test("constructor exposes every supplied decoration folder including embroidery", () => {
    const categories = ["prints", "rivets", "distress", "zippers", "pullers", "embroidery"];

    for (const category of categories) {
        assert.match(defaultDecorationsSource, new RegExp(`createRepeatedHardware\\('${category}'`));
        for (let imageIndex = 1; imageIndex <= 7; imageIndex += 1) {
            assert.equal(
                fs.existsSync(path.join(root, "public", "mock", category, `${imageIndex}.webp`)),
                true,
                `${category}/${imageIndex}.webp is missing`,
            );
        }
    }

    assert.match(defaultDecorationsSource, /src: `\/mock\/\$\{categoryId\}\/\$\{imageIndex\}\.webp`/);
    assert.doesNotMatch(constructorSource, /isEmbroideryComingSoon|Вышивка скоро будет/);
});

test("catalog shows the constructor selection hint from the unfinished create action", () => {
    assert.match(landingSource, /selectForConstructor/);
    assert.match(popupSource, /Выберите вещь из каталога/);
    assert.match(popupSource, /НАЗАД/);
    assert.match(popupSource, /ДАЛЕЕ/);
    assert.match(popupSource, /export function CatalogHintPopup[\s\S]*?panelClassName="bg-\[#fff\]"[\s\S]*?backdropClassName="bg-black\/50"/s);
    assert.match(unfinishedSource, /\/\?selectForConstructor=1/);
    assert.match(unfinishedSource, /setBottomPanelState\("collapsed"\)[\s\S]*?window\.location\.replace\("\/\?selectForConstructor=1"\)/s);
    assert.match(landingSource, /router\.replace\('\/', \{ scroll: false \}\)/);
    assert.doesNotMatch(landingSource, /window\.history\.replaceState/);
});

test("unfinished deletion waits for confirmation in the shared popup style", () => {
    assert.match(unfinishedSource, /const \[isDeleteConfirmOpen, setIsDeleteConfirmOpen\] = useState\(false\)/);
    assert.match(unfinishedSource, /const handleDeleteSelectedItem = \(\) => \{[\s\S]*?setIsDeleteConfirmOpen\(true\)/s);
    assert.match(unfinishedSource, /const confirmDeleteSelectedItem = \(\) => \{[\s\S]*?removeSavedProfileItem/s);
    assert.match(unfinishedSource, /<UnfinishedDeletePopup[\s\S]*?onConfirm=\{confirmDeleteSelectedItem\}/s);
    assert.match(popupSource, /export function UnfinishedDeletePopup/);
    assert.match(popupSource, /Вы уверены, что хотите удалить\?/);
    assert.match(popupSource, /<ExitPopupButton onClick=\{onClose\}>ОТМЕНА<\/ExitPopupButton>/);
    assert.match(popupSource, /<ExitPopupButton onClick=\{onConfirm\}>УДАЛИТЬ<\/ExitPopupButton>/);
});

test("constructor exit controls share the save-or-leave popup", () => {
    assert.match(popupSource, /Вы уверены, что хотите выйти\?/);
    assert.match(popupBaseSource, /panelClassName/);
    assert.match(popupBaseSource, /viewportStyle\?: React\.CSSProperties/);
    assert.match(popupBaseSource, /className="viewportOverlayRoot z-\[2147483647\]/);
    assert.doesNotMatch(popupBaseSource, /ViewportOverlayChrome/);
    assert.match(globalStylesSource, /\.viewportOverlayRoot\s*\{[^}]*position:\s*fixed[^}]*inset:\s*0[^}]*box-sizing:\s*border-box/s);
    assert.doesNotMatch(globalStylesSource, /\.viewportOverlayChrome/);
    assert.match(popupBaseSource, /paddingTop: 'max\(1rem, env\(safe-area-inset-top\)\)'/);
    assert.match(popupBaseSource, /createPortal\([\s\S]*document\.body/);
    assert.match(popupBaseSource, /const lockedPathname = window\.location\.pathname/);
    assert.match(popupBaseSource, /if \(html\.style\.overflow === lockedHtmlOverflow\) html\.style\.overflow = previousHtmlOverflow/);
    assert.match(popupBaseSource, /if \(body\.style\.overflow === lockedBodyOverflow\) body\.style\.overflow = previousBodyOverflow/);
    assert.match(popupBaseSource, /if \(window\.location\.pathname === lockedPathname\)/);
    assert.match(popupSource, /panelClassName="bg-\[#fff\]"/);
    assert.doesNotMatch(popupSource, /viewportStyle=\{\{ top: "max\(10px, env\(safe-area-inset-top\)\)", bottom: "max\(10px, env\(safe-area-inset-bottom\)\)" \}\}/);
    assert.match(popupSource, /h-\[255px\]/);
    assert.match(popupSource, /pt-\[50px\]/);
    assert.match(popupSource, /pb-\[25px\]/);
    assert.match(popupSource, /text-\[12px\][^"]*font-medium[^"]*text-\[#A0A0A0\]/);
    assert.match(popupSource, /mt-\[8px\][^"]*text-\[10px\]/);
    assert.match(popupSource, /text-\[10px\][^"]*font-medium[^"]*text-\[#A0A0A0\]/);
    assert.match(popupSource, /mt-\[25px\][^"]*text-\[16px\]/);
    assert.match(popupSource, /text-\[16px\][^"]*font-medium[^"]*text-\[#2D2D2D\]/);
    assert.match(popupSource, /mt-\[30px\][^"]*gap-\[5px\]/);
    assert.match(popupSource, /gap-\[5px\]/);
    assert.match(popupSource, /h-\[30px\][^"]*w-\[150px\][^"]*rounded-\[5px\][^"]*bg-\[#FFF\]/);
    assert.match(popupSource, /shadow-\[0_0\.934px_1\.681px_0_rgba\(0,0,0,0\.26\)\]/);
    assert.match(popupSource, /EXIT_POPUP_BUTTON_BASE_CLASS = "[^"]*text-\[14px\][^"]*font-semibold[^"]*leading-\[11\.582px\]/);
    assert.doesNotMatch(popupSource, /subtle|text-\[#C4C4C4\]|underline-offset|shadow-none/);
    assert.match(popupSource, /<ExitPopupButton onClick=\{onLeave\}>НА ГЛАВНУЮ<\/ExitPopupButton>/);
    assert.match(popupSource, /EXIT_POPUP_BUTTON_BASE_CLASS\} text-\[#676767\] shadow-\[0_0\.934px_1\.681px_0_rgba\(0,0,0,0\.26\)\]/);
    assert.match(popupSource, /Сохранить в личном кабинете\?/);
    assert.match(popupSource, /НА ГЛАВНУЮ/);
    assert.match(popupSource, /СОХРАНИТЬ/);
    assert.match(constructorSource, /setIsExitPopupOpen\(true\)/);
    assert.match(constructorSource, /saveConstructorDraft/);
    assert.match(constructorSource, /const handleSaveDraft = \(\) => \{[\s\S]*setIsExitPopupOpen\(false\);[\s\S]*router\.push\("\/unfinished"\);/);
    assert.match(constructorSource, /router\.push\("\/unfinished"\)/);
    assert.doesNotMatch(constructorSource, /\/lk\?tab=unfinished/);
    assert.match(savedItemsSource, /CONSTRUCTOR_DRAFTS_STORAGE_KEY/);
    assert.match(constructorSource, /aria-label="Назад"/);
    assert.match(constructorSource, /left-\[10px\]\s+top-\[10px\]/);
    assert.match(constructorSource, /h-\[30px\]\s+w-\[30px\]/);
    assert.doesNotMatch(constructorSource, /aria-label="Открыть подсказку конструктора"/);
});

test("constructor popups cover the viewport without resizing the constructor or adding chrome strips", () => {
    assert.match(constructorSource, /const CONSTRUCTOR_OVERLAY_VIEWPORT_STYLE = \{[\s\S]*position: "fixed",[\s\S]*inset: 0,[\s\S]*width: "100%"/);
    assert.doesNotMatch(constructorSource, /const isConstructorOverlayOpen/);
    assert.doesNotMatch(constructorSource, /constructorOverlayOpen|constructorViewportOverlayOpen/);
    assert.doesNotMatch(globalStylesSource, /constructorOverlayOpen|constructorViewportOverlayOpen/);
    assert.doesNotMatch(constructorSource, /ViewportOverlayChrome/);
    assert.match(constructorSource, /createPortal\(overlay, portalTarget\)/);
    assert.match(constructorSource, /isSizeModalOpen && instructionPortalTarget[\s\S]*createPortal\([\s\S]*<SizeFitModal[\s\S]*instructionPortalTarget/);
    assert.match(globalStylesSource, /\.constructorViewport\s*\{[^}]*height:\s*calc\(100dvh \+ 160px\)/s);
    assert.doesNotMatch(globalStylesSource, /\.constructorViewport\s*\{[^}]*position:\s*fixed/s);
    assert.match(globalStylesSource, /\.constructorVisibleViewport\s*\{[^}]*height:\s*100dvh/s);
    assert.doesNotMatch(globalStylesSource, /\.constructorVisibleViewport\s*\{[^}]*padding-top:\s*env\(safe-area-inset-top\)/s);
    assert.doesNotMatch(constructorSource, /document\.body\.style\.position = "fixed"/);
    assert.match(constructorSource, /window\.scrollTo\(0, 0\)/);
});

test("unfinished surface supports an overlay that closes from its back button", () => {
    assert.match(unfinishedSource, /isOverlay/);
    assert.match(unfinishedSource, /onClose/);
    assert.match(unfinishedSource, /overlayPage/);
    assert.match(unfinishedSource, /onClick=\{handleBack\}/);
    assert.doesNotMatch(constructorSource, /<UnfinishedSurface/);
    assert.match(unfinishedOverlayRouteSource, /<UnfinishedSurface/);
    assert.match(unfinishedOverlayRouteSource, /isOverlay/);
    assert.match(unfinishedOverlayRouteSource, /onClose=\{\(\) => router\.back\(\)\}/);
    assert.match(modalCatchAllSource, /return null/);
    assert.match(unfinishedStylesSource, /\.overlayPage\s*\{[^}]*z-index:\s*2147483646/s);
});

test("constructor popups match the fifty percent instruction overlay", () => {
    assert.match(popupBaseSource, /bg-black\/40/);
    assert.match(popupBaseSource, /backdropClassName = "bg-black\/40 backdrop-blur-\[3px\]"/);
    assert.match(popupBaseSource, /data-popup-backdrop/);
    assert.match(popupSource, /backdropClassName="bg-black\/50"/);
    assert.match(popupSource, /viewportStyle=\{CONSTRUCTOR_POPUP_VIEWPORT_STYLE\}/);
    assert.match(constructorSource, /viewportOverlayRoot z-\[2147483645\][^\n]*bg-black\/50/);
    assert.match(unfinishedStylesSource, /\.overlayPage\s*\{[^}]*background:\s*rgba\(0,\s*0,\s*0,\s*0\.5\)/s);
});

test("constructor keeps selected garment size and only pans a zoomed canvas", () => {
    assert.match(canvasSource, /canPanStage/);
    assert.match(canvasSource, /initialModelIdRef/);
    assert.match(canvasSource, /useLayoutEffect/);
    assert.match(canvasSource, /if \(!isMounted\) return/);
    assert.match(canvasSource, /\[bottomInset,\s*selectedModel\?\.id,\s*isMounted\]/);
    assert.doesNotMatch(canvasSource, /setTimeout\(\(\) => updateSize\(true\), 100\)[\s\S]*\}, \[modelBounds\]\)/);
});

test("constructor size popup configures fit and saves it into cart order data", () => {
    assert.match(constructorSource, /type SleeveMode = "standard" \| "height"/);
    assert.match(constructorSource, /type GarmentFit = \{/);
    assert.match(constructorSource, /SIZE_FIT_RANGES/);
    assert.match(constructorSource, /S:\s*\{\s*length:\s*\{\s*min:\s*156,\s*max:\s*182/s);
    assert.match(constructorSource, /width:\s*\{\s*min:\s*70,\s*max:\s*84/s);
    assert.match(constructorSource, /Настройка посадки/);
    assert.match(constructorSource, /Рукава/);
    assert.match(constructorSource, /стандартные/);
    assert.match(constructorSource, /под рост/);
    assert.match(constructorSource, /FitSlider/);
    assert.match(constructorSource, /Длина/);
    assert.match(constructorSource, /Ширина/);
    assert.match(constructorSource, /productImageSrc/);
    assert.match(constructorSource, /z-\[2147483645\][^"]*bg-black\/50/);
    assert.match(constructorSource, /onClick=\{onClose\}/);
    assert.match(constructorSource, /event\.stopPropagation\(\)/);
    assert.doesNotMatch(constructorSource, /constructorSizeModal[^\n]*h-\[calc\(100dvh-10px\)\]/);
    assert.match(constructorSource, /rounded-\[15px\][^"]*bg-white[^"]*p-\[15px\]/);
    assert.match(constructorSource, /text-\[13px\][^"]*font-medium[^"]*leading-\[150%\]/);
    assert.match(constructorSource, /h-\[clamp\(210px,32dvh,300px\)\]/);
    assert.match(constructorSource, /match_size\.svg/);
    assert.match(constructorSource, /alert\.svg/);
    assert.match(constructorSource, /mt-\[clamp\(15px,2\.5dvh,25px\)\]/);
    assert.match(constructorSource, /mt-\[clamp\(12px,2dvh,20px\)\]/);
    assert.match(constructorSource, /gap-\[12px\]/);
    assert.match(constructorSource, /grid w-full grid-cols-\[minmax\(70px,85px\)_minmax\(0,238\.017px\)\]/);
    assert.match(constructorSource, /col-start-2 mt-\[7px\][^"]*text-\[8px\]/);
    assert.doesNotMatch(constructorSource, /<div>\s*<div className="flex h-\[30px\] w-\[220px\]/);
    assert.doesNotMatch(constructorSource, /closest\("button, input, textarea, select, a"\)/);
    assert.match(constructorSource, /closest\("input, textarea, select, a, \[data-panel-handle\], \[data-decoration-scroller\]"\)/);
    assert.match(constructorSource, /ref=\{decorationsScrollerRef\}[\s\S]{0,80}data-decoration-scroller/);
    assert.match(constructorSource, /mt-\[clamp\(20px,3dvh,35px\)\]/);
    assert.match(constructorSource, /gap-\[clamp\(20px,3dvh,35px\)\]/);
    assert.doesNotMatch(constructorSource, /mt-\[35px\][^"]*gap-\[1px\]/);
    assert.doesNotMatch(constructorSource, /mt-\[35px\][^"]*gap-\[25px\]/);
    assert.match(constructorSource, /mt-\[clamp\(20px,3\.5dvh,40px\)\]/);
    assert.match(constructorSource, /grid-cols-\[minmax\(70px,85px\)_minmax\(0,238\.017px\)\]/);
    assert.match(constructorSource, /grid w-full grid-cols-\[minmax\(70px,85px\)_minmax\(0,238\.017px\)\] items-center justify-around gap-\[5px\]/);
    assert.match(constructorSource, /flex h-full w-full justify-center pl-\[20px\]/);
    assert.match(constructorSource, /gap-\[5px\] font-manrope/);
    assert.doesNotMatch(constructorSource, /grid-cols-\[64px_minmax\(0,238\.017px\)\] items-center gap-\[14px\]/);
    assert.match(constructorSource, /text-\[13px\][^"]*font-medium[^"]*leading-\[150%\][^"]*text-black/);
    assert.match(constructorSource, /w-full[^"]*whitespace-nowrap[^"]*text-\[8px\][^"]*font-medium[^"]*leading-\[150%\][^"]*text-\[#B8B8B8\]/);
    assert.doesNotMatch(constructorSource, /text-\[23px\] font-medium leading-none text-black/);
    assert.match(constructorSource, /const SIZE_MODAL_MODEL_HEIGHT_CM = 168/);
    assert.match(constructorSource, /Рост \{SIZE_MODAL_MODEL_HEIGHT_CM\}/);
    assert.doesNotMatch(constructorSource, /<p>Рост \{draftFit\.lengthCm\}<\/p>/);
    assert.match(constructorSource, /const standardFit = createDefaultFit\([\s\S]*getProductDimensions\(product, draftFit\.selectedSize\)/);
    assert.match(constructorSource, /flex flex-col">[\s\S]*Длина: \{standardFit\.lengthCm\}[\s\S]*Ширина: \{standardFit\.widthCm\}/);
    assert.doesNotMatch(constructorSource, /<span>Длина: \{draftFit\.lengthCm\}<\/span>/);
    assert.doesNotMatch(constructorSource, /<span>Ширина: \{draftFit\.widthCm\}<\/span>/);
    assert.match(constructorSource, /h-\[30px\] w-\[38px\][^"]*text-\[18px\][^"]*font-light[^"]*leading-normal[^"]*tracking-\[-0\.36px\]/);
    assert.doesNotMatch(constructorSource, /background:\s*"linear-gradient\(180deg, #F3F3F3 -0\.72%, #E7E7E7 100\.37%\)"/);
    assert.match(constructorSource, /borderRadius:\s*"4px"/);
    assert.match(constructorSource, /boxShadow:\s*"0 2px 4px 0 rgba\(0, 0, 0, 0\.25\) inset"/);
    assert.doesNotMatch(constructorSource, /h-\[30px\] w-\[38px\][^"]*shadow-\[0_0\.934px_1\.681px_0_rgba\(0,0,0,0\.26\)\]/);
    assert.match(constructorSource, /<p className="mt-\[15px\] whitespace-nowrap">/);
    assert.doesNotMatch(constructorSource, /text-\[24px\] font-light leading-none/);
    assert.match(constructorSource, /<p className="col-start-2 mt-\[7px\]/);
    assert.match(constructorSource, /Соответствуют размеру/);
    assert.match(constructorSource, /mt-\[clamp\(20px,3\.5dvh,40px\)\][^"]*justify-center[^"]*gap-\[5px\]/);
    assert.match(constructorSource, /onClick=\{handleReset\}[\s\S]*text-\[#C4C4C4\][^"]*underline[^"]*decoration-\[8%\][^"]*underline-offset-\[20%\][^"]*shadow-none/);
    assert.match(constructorSource, /\[text-decoration-skip-ink:auto\][^"]*\[text-decoration-style:solid\][^"]*\[text-underline-position:from-font\]/);
    assert.match(constructorSource, /onClick=\{\(\) => onSave\(draftFit\)\}[\s\S]*shadow-\[0_0\.934px_1\.681px_0_rgba\(0,0,0,0\.26\)\]/);
    assert.match(constructorSource, /w-\[238\.017px\][^"]*h-\[2px\][^"]*bg-\[#D3D3D3\]/);
    assert.match(constructorSource, /w-\[1\.983px\][^"]*h-\[4px\][^"]*bg-\[#D9D9D9\]/);
    assert.match(constructorSource, /width="12"[\s\S]*height="12"[\s\S]*fill="#D3D3D3"/);
    assert.match(constructorSource, /width="16"[\s\S]*height="16"[\s\S]*fill="black"/);
    assert.match(constructorSource, /top-\[-23px\][^"]*font-bold[^"]*text-black/);
    assert.match(constructorSource, /\{value\}/);
    assert.doesNotMatch(constructorSource, /labelValues/);
    assert.match(constructorSource, /mt-\[8px\][^"]*font-manrope[^"]*text-\[8px\][^"]*leading-\[150%\]/);
    assert.match(constructorSource, /standardSleeveLength = getFitRangeForSize\(draftFit\.selectedSize\)\.length\.defaultValue/);
    assert.match(constructorSource, /стандартные \$\{draftFit\.selectedSize\}\(\$\{standardSleeveLength\}\)/);
    assert.doesNotMatch(constructorSource, /стандартные \$\{draftFit\.selectedSize\}\(\$\{draftFit\.lengthCm\}\)/);
    assert.match(constructorSource, /рост \$\{standardSleeveLength\}/);
    assert.doesNotMatch(constructorSource, /Соответствуют размеру \$\{draftFit\.selectedSize\} - рост \$\{draftFit\.lengthCm\}/);
    assert.match(constructorSource, /className="viewportOverlayRoot[^"]*p-\[5px\]"/);
    assert.match(constructorSource, /className="viewportOverlayRoot[^"]*p-\[5px\]"/);
    assert.match(constructorSource, /constructorSizeModal[^\n]*w-full[^\n]*overflow-hidden/);
    assert.doesNotMatch(constructorSource, /max-w-\[356px\]|max-w-\[430px\]/);
    assert.doesNotMatch(constructorSource, /transform:\s*"scale\(/);
    assert.match(constructorSource, /onSave=\{handleSaveFit\}/);
    assert.match(constructorSource, /buildConstructorCustomization/);
    assert.match(constructorSource, /fit,\s*decorations,\s*totalPrice/s);
    assert.match(cartStoreSource, /ConstructorCustomization/);
    assert.match(constructorSource, /fit\?:\s*GarmentFit/);
    assert.match(cartPresentationSource, /Посадка:/);
    assert.match(checkoutSource, /Посадка:/);
    assert.match(orderContentSource, /Посадка:/);
});

test("constructor can edit an existing cart item without creating a duplicate", () => {
    assert.doesNotMatch(constructorSource, /isConstructorCartDisabled = true/);
    assert.match(constructorSource, /editCartItemId/);
    assert.match(constructorSource, /editingCartItem/);
    assert.match(constructorSource, /loadedEditCartItemIdRef/);
    assert.match(constructorSource, /if \(editCartItemId\) return editingCartItem/);
    assert.match(constructorSource, /setIsCartOpen\(false\)/);
    assert.match(constructorSource, /}, \[editCartItemId, setIsCartOpen\]\)/);
    assert.match(constructorSource, /setPlacedItemsByView\(\(\{/);
    assert.match(constructorSource, /updateItem\(editingCartItem\.id,\s*cartPayload\)/);
    assert.match(constructorSource, /addItem\(cartPayload\)/);
    assert.match(cartStoreSource, /updateItem:\s*\(id:\s*string,\s*item:\s*Omit<CartItem,\s*'id'>\) => void/);
    assert.doesNotMatch(constructorSource, /<CartOverlay/);
    assert.match(constructorSource, /setIsCartOpen\(true\)/);
});

test("constructor buy opens the expanded shared cart action bar", () => {
    assert.match(constructorSource, /import \{ CartActionBar \} from "@\/components\/cart\/CartActionBar"/);
    assert.match(constructorSource, /const \{ items, activeItemId, addItem, updateItem, setIsCartOpen \} = useCartStore\(\)/);
    assert.match(constructorSource, /const constructorCartItem = useMemo\(/);
    assert.match(constructorSource, /setIsCartOpen\(true\)/);
    assert.match(constructorSource, /<CartActionBar[\s\S]*?visible=\{false\}[\s\S]*?cartItemId=\{constructorCartItem\?\.id\}[\s\S]*?usePreferredCartItemOnly[\s\S]*?onBuy=\{\(\) => router\.push\("\/checkout"\)\}/);
    assert.doesNotMatch(constructorSource, /<CartOverlay/);
});

test("constructor centers the garment above controls and avoids faded grid swaps", () => {
    assert.match(constructorSource, /bottomInset=\{canvasBottomInset\}/);
    assert.match(canvasSource, /getVisibleCanvasHeight/);
    assert.doesNotMatch(constructorSource, /isExpandedGridVisible/);
    assert.doesNotMatch(constructorSource, /PANEL_TRANSITION_MS/);
    assert.match(constructorSource, /decorationViewportHeight/);
    assert.match(constructorSource, /transition-\[max-height\]/);
    assert.match(constructorSource, /overflow-hidden/);
    assert.match(constructorSource, /\[isPanelExpanded,\s*selectedCategory\]/);
});

test("constructor panel has rounded actions, expanded total, comments, and two-row expanded choices", () => {
    assert.match(constructorSource, /rounded-\[15px\]/);
    assert.match(constructorSource, /left-\[5px\]\s+right-\[5px\]/);
    assert.match(constructorSource, /md:w-\[min\(600px,calc\(100%-10px\)\)\]/);
    assert.doesNotMatch(constructorSource, /className="absolute left-0 right-0 z-20/);
    assert.doesNotMatch(constructorSource, /bottom-\[13px\]/);
    assert.doesNotMatch(constructorSource, /НА ГЛАВНУЮ/);
    assert.doesNotMatch(constructorSource, /\? "СОХРАНИТЬ" : "НА ГЛАВНУЮ"/);
    assert.match(constructorSource, /onClick=\{handlePanelSecondaryAction\}[\s\S]*СОХРАНИТЬ/);
    assert.match(constructorSource, /ДАЛЕЕ/);
    assert.match(constructorSource, /absolute bottom-0 left-0 right-0 z-10 flex h-\[35px\] items-center justify-between bg-white px-\[40px\]/);
    assert.doesNotMatch(constructorSource, /right-\[calc\(50%_\+_55px\)\]/);
    assert.doesNotMatch(constructorSource, /left-\[calc\(50%_\+_55px\)\]/);
    assert.match(constructorSource, /className="flex h-full w-\[100px\] items-center justify-center appearance-none bg-transparent text-center transition active:scale-95"/);
    assert.match(constructorSource, /className="h-\[15px\] w-\[2px\] shrink-0 rounded-\[15px\] bg-\[#9D9D9D\]/);
    assert.match(constructorSource, /Комментарий/);
    assert.match(constructorSource, /Итого/);
    assert.doesNotMatch(constructorSource, /\?:\s*"mt-\[9px\]\s+text-\[12px\]"/);
    assert.match(constructorSource, /const DECORATION_PAGE_SIZE = 10/);
    assert.match(constructorSource, /text-\[12px\]/);
    assert.match(constructorSource, /gap-\[30px\]/);
    assert.match(constructorSource, /const expandedPanelHeight = 500/);
    assert.doesNotMatch(constructorSource, /expandedPanelHeight = isCustomizationDetailsOpen/);
    assert.match(constructorSource, /bottom-\[75px\]/);
    assert.match(constructorSource, /h-\[190px\]/);
    assert.match(constructorSource, /isCustomizationDetailsOpen \? "pt-0" : "pt-\[36px\]"/);
    assert.match(constructorSource, /h-\[190px\] overflow-hidden/);
    assert.match(constructorSource, /transition-transform duration-500 ease-out/);
    assert.match(constructorSource, /isPanelExpanded \? "translate-y-0" : "translate-y-full"/);
    assert.match(constructorSource, /isPanelExpanded \? "pointer-events-auto" : "pointer-events-none"/);
    assert.doesNotMatch(constructorSource, /bottom-\[-205px\]/);
    assert.doesNotMatch(constructorSource, /transition-\[bottom\]/);
    assert.doesNotMatch(constructorSource, /transition-\[opacity,transform\]/);
    assert.match(constructorSource, /min-h-0 flex-1 overflow-y-auto/);
    assert.match(constructorSource, /flex shrink-0 items-center justify-between text-\[14px\]/);
    assert.match(constructorSource, /max-h-\[120px\]/);
    assert.doesNotMatch(constructorSource, /visualViewport/);
    assert.doesNotMatch(constructorSource, /keyboardInset/);
    assert.match(constructorSource, /const panelBottom = "var\(--constructor-panel-bottom, 5px\)"/);
    assert.match(constructorSource, /const panelBottomForCanvas = 10/);
    assert.doesNotMatch(constructorSource, /keyboardPanelLift/);
    assert.doesNotMatch(constructorSource, /isCommentFocused/);
    assert.match(constructorSource, /resetConstructorViewportAfterKeyboard/);
    assert.match(constructorSource, /window\.scrollTo\(0, 0\)/);
    assert.match(constructorSource, /document\.documentElement\.scrollTop = 0/);
    assert.match(constructorSource, /document\.body\.scrollTop = 0/);
    assert.match(constructorSource, /onBlur=\{\(\) => \{[\s\S]*resetConstructorViewportAfterKeyboard\(\);[\s\S]*window\.setTimeout\(resetConstructorViewportAfterKeyboard, 120\);[\s\S]*window\.setTimeout\(resetConstructorViewportAfterKeyboard, 320\);[\s\S]*\}\}/);
    assert.match(constructorSource, /text-\[16px\][^"]*placeholder:text-\[12px\]/);
    assert.doesNotMatch(constructorSource, /pb-\[61px\]/);
    assert.match(constructorSource, /text-\[10px\][^"]*[\s\S]*\{modelView === "front" \? "вид спереди" : "вид сзади"\}/);
    assert.match(constructorSource, /text-\[10px\][^"]*[\s\S]*<span>повернуть<\/span>/);
});

test("constructor starts with a dismissible instruction overlay", () => {
    assert.match(constructorSource, /isInstructionMounted/);
    assert.doesNotMatch(constructorSource, /isInstructionVisible/);
    assert.doesNotMatch(constructorSource, /instructionDismissTimerRef/);
    assert.match(constructorSource, /const \[isInstructionMounted, setIsInstructionMounted\] = useState\(!initialDraftId\)/);
    assert.match(constructorSource, /const instructionPortalTarget = useConstructorPageEnvironment\(isConstructorOverlayActive\)/);
    assert.match(constructorSource, /useSyncExternalStore\([\s\S]*getDocumentBody[\s\S]*getServerDocumentBody/);
    assert.match(constructorSource, /const isConstructorOverlayActive = isInstructionMounted \|\| isSizeModalOpen \|\| isExitPopupOpen/);
    assert.match(constructorSource, /const applyOverlayChrome = \(\) => \{[\s\S]*html\.dataset\.constructorOverlayActive = "true"[\s\S]*metaThemeColor\.content = "#FFFFFF"/);
    assert.match(constructorSource, /overlayThemeRefreshTimer = window\.setTimeout\(applyOverlayChrome, 120\)/);
    assert.match(globalStylesSource, /data-constructor-overlay-active="true"/);
    assert.match(globalStylesSource, /html\[data-app-page="constructor"\],\s*html\[data-app-page="constructor"\] body,[\s\S]*background-color:\s*#FFFFFF/s);
    assert.doesNotMatch(globalStylesSource, /app-viewport-bottom-extension/);
    assert.doesNotMatch(globalStylesSource, /constructorVisibleViewport::after/);
    assert.match(globalStylesSource, /body\[data-app-page="constructor"\]\[data-constructor-overlay-active="true"\] \.appSafariTopBar/);
    assert.doesNotMatch(constructorSource, /instructionImage/);
    assert.match(constructorSource, /Закрыть инструкцию конструктора/);
    assert.match(constructorSource, /z-\[2147483646\]/);
    assert.match(constructorSource, /bg-black\/50/);
    assert.match(constructorSource, /className="viewportOverlayRoot z-\[2147483646\][^"]*bg-black\/50/);
    assert.doesNotMatch(constructorSource, /ViewportOverlayChrome/);
    assert.doesNotMatch(constructorSource, /className="fixed inset-0[^"]*overflow-visible[^"]*bg-black\/50/);
    assert.doesNotMatch(constructorSource, /absolute left-0 right-0 top-\[-120px\] h-\[120px\] bg-black\/50/);
    assert.doesNotMatch(constructorSource, /absolute bottom-\[-120px\] left-0 right-0 h-\[120px\] bg-black\/50/);
    assert.match(constructorSource, /paddingTop: "max\(52px, calc\(env\(safe-area-inset-top\) \+ 42px\)\)"/);
    assert.match(constructorSource, /px-\[15px\]/);
    assert.doesNotMatch(constructorSource, /className="fixed inset-0[^"]*inset-\[-120px\]/);
    assert.match(constructorSource, /style=\{CONSTRUCTOR_INSTRUCTION_OVERLAY_VIEWPORT_STYLE\}/);
    assert.doesNotMatch(constructorSource, /className=\{`fixed inset-0[^`]*duration-500/);
    assert.match(constructorSource, /createPortal\(overlay, portalTarget\)/);
    assert.match(constructorSource, /src="\/instuction\.webp"/);
    assert.match(constructorSource, /width=\{265\}[\s\S]*height=\{150\}[\s\S]*priority[\s\S]*unoptimized/);
    assert.doesNotMatch(constructorSource, /import NextImage from "next\/image"/);
    assert.match(constructorSource, /setIsInstructionMounted\(false\)/);
    assert.match(constructorSource, /if \(!isOpen\) return null/);
    assert.match(constructorSource, /h-\[clamp\(125px,40\.54vw,150px\)\]/);
    assert.match(constructorSource, /w-\[clamp\(220px,71\.62vw,265px\)\]/);
    assert.match(constructorSource, /selectedSize \? `Размер: \$\{selectedSize\}` : "Цвет\/Размер"/);
    assert.match(constructorSource, /elevateSizeButton=\{isInstructionMounted && !isSizeModalOpen && !isExitPopupOpen\}/);
    assert.doesNotMatch(constructorSource, /min-w-\[96px\]/);
    assert.doesNotMatch(adaptiveHeaderSource, /styles\.headerElevated/);
    assert.match(adaptiveHeaderSource, /createPortal\(elevatedSizeButton, document\.body\)/);
    assert.match(adaptiveHeaderSource, /getBoundingClientRect\(\)/);
    assert.match(adaptiveHeaderSource, /visibility:\s*"hidden"/);
    assert.match(adaptiveHeaderStylesSource, /\.sizeButtonElevated\s*\{[^}]*z-index:\s*2147483647/s);
    assert.match(adaptiveHeaderSource, /isConstructor && elevateSizeButton/);
    assert.match(adaptiveHeaderSource, /typeof document !== "undefined"/);
    assert.match(adaptiveHeaderSource, /elevateSizeButton/);
    assert.match(adaptiveHeaderStylesSource, /\.sizeButtonElevated\s*\{/);
    assert.match(adaptiveHeaderStylesSource, /\.sizeButtonElevated\s*\{[^}]*position:\s*fixed/s);
    assert.doesNotMatch(adaptiveHeaderStylesSource, /\.headerElevated/);
    assert.doesNotMatch(adaptiveHeaderStylesSource, /top:\s*calc\(var\(--header-top-offset,\s*0px\) \+ 10px\)/);
    assert.doesNotMatch(adaptiveHeaderStylesSource, /z-index:\s*180/);
    assert.match(popupBaseSource, /z-\[2147483647\]/);
});

test("offer bypasses the splash and has no back control", () => {
    assert.match(splashSource, /const isOfferRoute = pathname === '\/offer'/);
    assert.match(splashSource, /const isHiddenRoute = isSplashHiddenRoute\(pathname\)/);
    assert.match(splashSource, /if \(isOfferRoute\) \{[\s\S]*splashWindow\[SPLASH_APP_RUN_KEY\] = true;[\s\S]*sessionStorage\.setItem\(SPLASH_SESSION_KEY, 'done'\)/);
    assert.doesNotMatch(offerSource, /FiArrowLeft|aria-label="Вернуться с оферты"|title="Назад"/);
});

test("constructor preloads both garment sides before rotation", () => {
    assert.match(constructorSource, /\[frontImage,\s*backImage\]\.filter\(Boolean\)\.forEach/);
    assert.match(constructorSource, /const versionedSrc = versionConstructorMedia\(src\)/);
    assert.match(constructorSource, /const preloadImage = new window\.Image\(\)/);
    assert.match(constructorSource, /preloadImage\.src = versionedSrc/);
});

test("login stays an empty shell while account renders the profile surface", () => {
    assert.match(lkPageSource, /<UnfinishedSurface\s+initialTab="profile"\s+\/>/);
    assert.match(loginPageSource, /aria-label="Вход"/);
    assert.doesNotMatch(lkPageSource, /Страница в разработке|Личный кабинет<\/Text>|aria-label="Личный кабинет"/);
});

test("PWA launches always show the splash screen once per app run", () => {
    assert.match(splashSource, /display-mode: standalone/);
    assert.match(splashSource, /standaloneNavigator\.standalone === true/);
    assert.match(splashSource, /PWA_REFRESH_SPLASH_SKIP_KEY = 'p2o_skip_splash_once'/);
    assert.match(splashSource, /const skipAfterPullRefresh = sessionStorage\.getItem\(PWA_REFRESH_SPLASH_SKIP_KEY\) === '1'/);
    assert.match(splashSource, /sessionStorage\.removeItem\(PWA_REFRESH_SPLASH_SKIP_KEY\)/);
    assert.match(splashSource, /alreadyShown = !isStandaloneApp && sessionStorage\.getItem\(SPLASH_SESSION_KEY\)/);
    assert.match(splashSource, /__p2oSplashHandledThisAppRun/);
    assert.match(splashSource, /splashWindow\[SPLASH_APP_RUN_KEY\]/);
    assert.doesNotMatch(splashSource, /handledThisAppRunRef/);
});

test("splash waits for hydration before mounting the video surface", () => {
    assert.match(splashSource, /const \[show, setShow\] = useState\(false\)/);
    assert.match(splashSource, /className="appSplashScreen"/);
    assert.match(splashSource, /const openTimer = window\.setTimeout\(\(\) => setShow\(true\), 0\)/);
    assert.doesNotMatch(layoutSource, /SPLASH_BOOTSTRAP_SCRIPT|p2o-splash-bootstrap|suppressHydrationWarning/);
    assert.doesNotMatch(globalStylesSource, /data-p2o-splash/);
});

test("splash keeps the animated logo hidden until it is actually playing", () => {
    assert.match(splashSource, /href="\/logo_anim\.mp4" as="video" type="video\/mp4"/);
    assert.doesNotMatch(splashSource, /pwa-icon-source\.png|poster=/);
    assert.match(splashSource, /opacity:\s*logoReady \? 1 : 0/);
    assert.match(splashSource, /transition:\s*'opacity 120ms ease-out'/);
    assert.match(splashSource, /video\.defaultMuted = true/);
    assert.match(splashSource, /video\.setAttribute\('muted', ''\)/);
    assert.match(splashSource, /video\.setAttribute\('webkit-playsinline', ''\)/);
    assert.match(splashSource, /video\.removeAttribute\('controls'\)/);
    assert.match(splashSource, /const videoQueueFallbackTimer = window\.setTimeout\([\s\S]*?setVideoStatus\('logo', 'loaded'\)[\s\S]*?1600\)/);
    assert.doesNotMatch(splashSource, /if \(!show \|\| !logoReady\) return/);
    assert.match(splashSource, /onError=\{handleLogoError\}/);
});

test("splash retries muted inline autoplay and reveals the video only on playing", () => {
    assert.match(splashSource, /const handleLogoPlaying = \(\) => \{[\s\S]*?setLogoReady\(true\)/);
    assert.match(splashSource, /onCanPlayThrough=\{tryPlayLogo\}/);
    assert.match(splashSource, /onCanPlay=\{tryPlayLogo\}/);
    assert.match(splashSource, /onLoadedMetadata=\{tryPlayLogo\}/);
    assert.match(splashSource, /onLoadedData=\{tryPlayLogo\}/);
    assert.match(splashSource, /onPlaying=\{handleLogoPlaying\}/);
    assert.match(splashSource, /const retryTimers = \[0, 180, 600\]/);
    assert.match(splashSource, /window\.addEventListener\('pageshow', resumePlayback\)/);
    assert.match(splashSource, /controls=\{false\}/);
    assert.match(splashSource, /pointerEvents:\s*'none'/);
    assert.match(globalStylesSource, /\.appSplashScreen video::\-webkit-media-controls-start-playback-button/);
});

test("constructor has a compact back button and updated rotate controls", () => {
    assert.match(constructorSource, /aria-label="Назад"[\s\S]{0,300}rotateButtonGlassStyle/);
    assert.match(constructorSource, /width="21"\s+height="24"/);
    assert.match(constructorSource, /h-\[45px\]\s+w-\[90px\][^"]*rounded-\[14px\]/);
    assert.match(constructorSource, /text-\[10px\][^"]*uppercase[^"]*text-\[#A0A0A0\]/);
});

test("constructor defers changing the active decoration until a clean tap ends", () => {
    assert.match(canvasSource, /shouldDeferHardwareSelection/);
    assert.match(canvasSource, /deferredHardwareSelectionRef/);
    assert.match(canvasSource, /!isPinchingRef\.current/);
});

test("dismissing the expanded panel from the canvas cannot drag the selected decoration", () => {
    assert.match(canvasSource, /data-constructor-canvas="true"/);
    assert.match(
        constructorSource,
        /target\.closest\('\[data-constructor-canvas="true"\]'\)[\s\S]*?event\.preventDefault\(\);[\s\S]*?event\.stopPropagation\(\);/,
    );
});

test("constructor drops newly added decorations next to existing ones", () => {
    assert.match(constructorSource, /getNextDecorationDropPosition/);
    assert.match(constructorSource, /existingItems:\s*prev\[modelView\]/);
    assert.doesNotMatch(constructorSource, /x:\s*centerPoint\.x,\s*y:\s*centerPoint\.y/);
});

test("zoomed constructor canvas can move every garment edge to the center", () => {
    assert.match(canvasSource, /getStagePanBounds/);
    assert.match(canvasSource, /bottomInset/);
});

test("constructor keeps the top safe area white and extends the backdrop through the bottom safe area", () => {
    assert.match(layoutSource, /viewportFit:\s*"cover"/);
    assert.match(layoutSource, /colorScheme:\s*"light"/);
    assert.doesNotMatch(layoutSource, /black-translucent/);
    assert.match(layoutSource, /AppEnvironment/);
    assert.match(appEnvironmentSource, /constructor[\s\S]*#FFFFFF/);
    assert.doesNotMatch(appEnvironmentSource, /surface === "safari26" && pageChrome\.page/);
    assert.match(appEnvironmentSource, /page:\s*"catalog"[\s\S]*topColor:\s*"#F2F2F2"/);
    assert.match(appEnvironmentSource, /const topColor = pageChrome\.topColor/);
    assert.match(appEnvironmentSource, /const isConstructorOverlayActive = pageChrome\.page === "constructor"/);
    assert.match(appEnvironmentSource, /const activeTopColor = isConstructorOverlayActive \? "#FFFFFF" : topColor/);
    assert.match(appEnvironmentSource, /metaThemeColor\.content = activeTopColor/);
    assert.match(globalStylesSource, /appSafariTopBar/);
    assert.doesNotMatch(globalStylesSource, /appSafariBottomBar/);
    assert.match(constructorSource, /constructorSafariTop/);
    assert.doesNotMatch(constructorSource, /constructorSafariBottom/);
    assert.match(constructorSource, /constructorVisibleViewport/);
    assert.match(constructorSource, /className="constructorHeaderFlush"/);
    assert.match(globalStylesSource, /\.constructorSafariTop\s*\{[^}]*z-index:\s*79/s);
    assert.match(globalStylesSource, /\.constructorHeaderFlush\s*\{[^}]*margin-top:\s*0\s*!important/s);
    assert.match(globalStylesSource, /\.constructorViewport\s*\{[^}]*calc\(100dvh \+ 160px\)/s);
    assert.doesNotMatch(globalStylesSource, /\.constructorViewport\s*\{[^}]*position:\s*fixed/s);
    assert.match(globalStylesSource, /\.constructorVisibleViewport\s*\{[^}]*height:\s*100dvh/s);
    assert.doesNotMatch(globalStylesSource, /\.constructorVisibleViewport\s*\{[^}]*padding-top:\s*env\(safe-area-inset-top\)/s);
    assert.match(globalStylesSource, /--constructor-panel-bottom:\s*5px/);
    assert.doesNotMatch(globalStylesSource, /--constructor-panel-bottom:\s*0px/);
    assert.doesNotMatch(globalStylesSource, /html\[data-browser-surface="pwa"\]\[data-app-page="constructor"\] \.constructorViewport\s*\{[^}]*--constructor-panel-bottom:\s*40px/s);
    assert.doesNotMatch(globalStylesSource, /--constructor-panel-bottom:\s*40px/);
    assert.doesNotMatch(globalStylesSource, /constructorSafariBottom/);
    assert.match(globalStylesSource, /height:\s*max\(10px,\s*env\(safe-area-inset-top\)\)/);
    assert.doesNotMatch(globalStylesSource, /catalogSafariTop/);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\]\[data-app-page="catalog"\] \.appSafariTopBar/);
    assert.match(globalStylesSource, /html\[data-app-page="constructor"\]\[data-browser-surface="pwa"\] \.appSafariTopBar/);
    assert.doesNotMatch(globalStylesSource, /appSafariBottomBar/);
    assert.doesNotMatch(globalStylesSource, /\.constructorViewport\s*\{[^}]*padding-top:\s*env\(safe-area-inset-top\)/s);
    assert.match(globalStylesSource, /safe-area-inset-top/);
    assert.match(globalStylesSource, /:root\s*\{[^}]*color-scheme:\s*light[^}]*background-color:\s*#F2F2F2/s);
    assert.match(globalStylesSource, /html\[data-app-page="constructor"\],\s*html\[data-app-page="constructor"\] body,\s*html\[data-app-page="constructor"\] \.appPageShell\s*\{[^}]*background-color:\s*#FFFFFF/s);
    assert.doesNotMatch(globalStylesSource, /app-viewport-bottom-extension|app-visual-viewport-bottom-offset/);
    assert.doesNotMatch(globalStylesSource, /constructorVisibleViewport::after/);
    assert.doesNotMatch(globalStylesSource, /\.constructorVisibleViewport\s*\{[^}]*padding-bottom/s);
    assert.doesNotMatch(globalStylesSource, /data-app-page="constructor"\] \.viewportOverlayRoot,[\s\S]*bottom:\s*calc\(-1 \* env\(safe-area-inset-bottom\)\)/s);
    assert.match(adaptiveHeaderStylesSource, /:global\(html\[data-app-page="constructor"\]\[data-browser-surface="pwa"\]\) \.constructor\s*\{[^}]*padding-top:\s*env\(safe-area-inset-top\)/s);
    assert.doesNotMatch(adaptiveHeaderStylesSource, /data-browser-surface="safari26"[^\n]*\.constructor/);
    assert.match(popupBaseSource, /paddingBottom: 'max\(1rem, env\(safe-area-inset-bottom\)\)'/);
    assert.match(constructorSource, /const CONSTRUCTOR_OVERLAY_VIEWPORT_STYLE = \{[\s\S]*position: "fixed",[\s\S]*inset: 0,[\s\S]*width: "100%"/);
    assert.match(constructorSource, /const CONSTRUCTOR_INSTRUCTION_OVERLAY_VIEWPORT_STYLE = \{\s*\.\.\.CONSTRUCTOR_OVERLAY_VIEWPORT_STYLE,\s*paddingTop: "max\(52px, calc\(env\(safe-area-inset-top\) \+ 42px\)\)"/s);
    assert.match(constructorSource, /className="viewportOverlayRoot z-\[2147483645\] flex items-center justify-center bg-black\/50 p-\[5px\]"/);
    assert.match(constructorSource, /className="viewportOverlayRoot z-\[2147483646\] flex cursor-pointer items-start justify-end bg-black\/50 px-\[15px\]"/);
    assert.doesNotMatch(constructorSource, /ViewportOverlayChrome/);
    assert.match(constructorSource, /createPortal\(overlay, portalTarget\)/);
    assert.match(constructorSource, /style=\{CONSTRUCTOR_INSTRUCTION_OVERLAY_VIEWPORT_STYLE\}/);
    assert.doesNotMatch(constructorSource, /rounded-\[15px\] bg-white shadow-\[0_4px_16\.8px_-1px_rgba\(0,0,0,0\.25\)\] transition-\[height\]/);
    assert.match(constructorSource, /rounded-\[15px\] bg-white transition-\[height\]/);
    assert.match(constructorSource, /const panelBottom = "var\(--constructor-panel-bottom, 5px\)"/);
    assert.match(constructorSource, /const rotateBottom = `calc\(var\(--constructor-panel-bottom, 5px\) \+ \$\{panelHeight \+ ROTATE_PANEL_GAP\}px\)`/);
});

test("size popup uses a swipeable Swiper gallery", () => {
    assert.match(constructorSource, /from "swiper\/react"/);
    assert.match(constructorSource, /from "swiper\/modules"/);
    assert.match(constructorSource, /import "swiper\/css"/);
    assert.match(constructorSource, /import "swiper\/css\/navigation"/);
    assert.match(constructorSource, /<Swiper[\s\S]*modules=\{\[Navigation\]\}[\s\S]*navigation/);
    assert.match(constructorSource, /className="size-fit-swiper h-full w-full"/);
    assert.match(globalStylesSource, /\.size-fit-swiper \.swiper-button-disabled\s*\{[^}]*display:\s*none/s);
    assert.match(globalStylesSource, /\.size-fit-swiper \.swiper-button-next,\s*\.size-fit-swiper \.swiper-button-prev\s*\{[^}]*color:\s*#717171/s);
    assert.doesNotMatch(constructorSource, /import "swiper\/css\/pagination"/);
    assert.doesNotMatch(constructorSource, /modules=\{\[Pagination\]\}/);
    assert.doesNotMatch(constructorSource, /pagination=\{\{ clickable: true \}\}/);
    assert.match(constructorSource, /<SwiperSlide>[\s\S]*Фото товара/);
    assert.match(constructorSource, /<SwiperSlide>[\s\S]*Схема замеров/);
    assert.doesNotMatch(constructorSource, /activeSlide/);
});

test("size popup keeps fit controls compact and uses the site typography", () => {
    assert.match(constructorSource, /constructorSizeModal[^\n]*w-full[^\n]*overflow-hidden/);
    assert.doesNotMatch(constructorSource, /constructorSizeModal[^\n]*h-\[calc\(100dvh-10px\)\]/);
    assert.doesNotMatch(constructorSource, /scale\(min\(calc\(\(100vw - 14px\)/);
    assert.doesNotMatch(constructorSource, /font-\[Inter\]/);
    assert.match(constructorSource, /mt-\[18px\] w-full whitespace-nowrap text-center text-\[8px\]/);
    assert.match(constructorSource, /const \[isInteracting, setIsInteracting\] = useState\(false\)/);
    assert.match(constructorSource, /h-\[16px\] w-\[16px\]/);
    assert.match(constructorSource, /width="16" height="16"/);
    assert.match(constructorSource, /top-\[-23px\][^"]*text-\[12px\]/);
    assert.match(constructorSource, /isInteracting \? "scale-\[1\.28\]" : "scale-100"/);
    assert.doesNotMatch(constructorSource, /scale-\[1\.45\]/);
    assert.match(constructorSource, /onPointerDown=\{\(\) => setIsInteracting\(true\)\}/);
    assert.match(constructorSource, /onPointerUp=\{\(\) => setIsInteracting\(false\)\}/);
});

test("catalog and drafts use the guarded constructor route", () => {
    assert.match(constructorRouteSource, /ConstructorPage/);
    assert.match(constructorRouteSource, /constructorRoute !== "constructor"/);
    assert.match(constructorRouteSource, /notFound\(\)/);
    assert.equal(fs.existsSync(path.join(root, "app", "constructor-builder", "page.tsx")), false);
    assert.equal(fs.existsSync(path.join(root, "app", "constructor", "page.tsx")), false);
    assert.match(productCardSource, /\/constructor\?productId=/);
    assert.match(mobileProductCardSource, /\/constructor\?productId=/);
    assert.match(unfinishedSource, /\/constructor\?productId=/);
    assert.match(unfinishedSource, /draftId=\$\{encodeURIComponent\(selectedDraft\.id\)\}/);
    assert.match(constructorRouteSource, /draftId=\{getSearchParam\(resolvedSearchParams, "draftId"\)\}/);
});

test("guarded constructor route lets the production root index render the catalog", () => {
    assert.match(constructorRouteSource, /import Home from "\.\.\/page"/);
    assert.match(constructorRouteSource, /constructorRoute === "index"/);
    assert.match(constructorRouteSource, /return <Home \/>/);
});
