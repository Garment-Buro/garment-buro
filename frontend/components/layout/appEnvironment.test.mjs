import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const layoutSource = fs.readFileSync(path.join(root, "app", "layout.tsx"), "utf8");
const manifestSource = fs.readFileSync(path.join(root, "app", "manifest.ts"), "utf8");
const globalStylesSource = fs.readFileSync(path.join(root, "app", "globals.css"), "utf8");
const headerStylesSource = fs.readFileSync(path.join(root, "components", "layout", "AdaptiveHeader.module.css"), "utf8");
const footerSource = fs.readFileSync(path.join(root, "components", "layout", "Footer.tsx"), "utf8");
const productPageSource = [
    path.join(root, "components", "product", "ProductPageClient.tsx"),
    path.join(root, "components", "product", "ProductMobileLayout.tsx"),
    path.join(root, "components", "product", "ProductDesktopLayout.tsx"),
    path.join(root, "hooks", "product", "useProductPage.ts"),
    path.join(root, "lib", "products", "constants.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const constructorSource = [
    path.join(root, "components", "constructor", "ConstructorPage.tsx"),
    path.join(root, "components", "constructor", "ConstructorWorkspace.tsx"),
    path.join(root, "components", "constructor", "ConstructorInstructionOverlay.tsx"),
    path.join(root, "hooks", "constructor", "useConstructorPageEnvironment.ts"),
    path.join(root, "lib", "constructor", "constants.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const environmentFiles = [
    path.join(root, "providers", "AppEnvironmentProvider.tsx"),
    path.join(root, "hooks", "browser", "useBrowserSurface.ts"),
    path.join(root, "lib", "browser", "utils", "detectBrowserSurface.ts"),
    path.join(root, "lib", "browser", "utils", "pageChrome.ts"),
];
const appEnvironmentSource = environmentFiles.map(file => fs.readFileSync(file, "utf8")).join("\n");

test("app environment wrapper exposes browser modes and per-page chrome colors", () => {
    assert.match(layoutSource, /AppEnvironment/);
    assert.match(layoutSource, /appPageShell/);
    assert.match(appEnvironmentSource, /useLayoutEffect/);
    assert.doesNotMatch(appEnvironmentSource, /\buseEffect\b/);

    assert.match(appEnvironmentSource, /pwa/);
    assert.match(appEnvironmentSource, /safari26/);
    assert.match(appEnvironmentSource, /safari18/);
    assert.match(appEnvironmentSource, /otherbrowser/);
    assert.match(appEnvironmentSource, /display-mode:\s*standalone/);
    assert.match(appEnvironmentSource, /targetNavigator\.standalone/);

    assert.match(appEnvironmentSource, /page:\s*"catalog"[\s\S]*topColor:\s*"#F2F2F2"[\s\S]*pageColor:\s*"#F2F2F2"/);
    assert.match(appEnvironmentSource, /page:\s*"constructor"[\s\S]*topColor:\s*"#FFFFFF"[\s\S]*pageColor:\s*"#FFFFFF"/);
    assert.match(appEnvironmentSource, /page:\s*"product"[\s\S]*topColor:\s*"#F2F2F2"[\s\S]*pageColor:\s*"#F2F2F2"/);
    assert.doesNotMatch(appEnvironmentSource, /bottomColor/);
    assert.match(appEnvironmentSource, /theme-color/);
    assert.match(appEnvironmentSource, /--app-page-bottom-offset/);
    assert.match(appEnvironmentSource, /--app-top-color/);
    assert.doesNotMatch(appEnvironmentSource, /--app-bottom-color/);
    assert.doesNotMatch(appEnvironmentSource, /SAFARI_26_TOP_COLOR/);
    assert.match(appEnvironmentSource, /const topColor = pageChrome\.topColor/);
    assert.doesNotMatch(appEnvironmentSource, /surface === "pwa" && pageChrome\.page === "catalog"/);
    assert.doesNotMatch(appEnvironmentSource, /surface === "safari26" && pageChrome\.page/);
    assert.doesNotMatch(appEnvironmentSource, /html\.style\.backgroundColor/);
    assert.doesNotMatch(appEnvironmentSource, /body\.style\.backgroundColor/);
    assert.doesNotMatch(appEnvironmentSource, /previousHtmlBackground|previousBodyBackground/);
});

test("global page shell paints only top Safari chrome and leaves the bottom viewport unmasked", () => {
    assert.match(globalStylesSource, /\.appPageShell\s*\{[^}]*100dvh/s);
    assert.match(globalStylesSource, /\.appPageShell\s*\{[^}]*padding-bottom:\s*var\(--app-page-bottom-offset/s);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\][\s\S]*--app-page-bottom-offset:\s*0px/s);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\],[\s\S]*html\[data-browser-surface="safari26"\],[\s\S]*html\[data-browser-surface="safari18"\]\s*\{[^}]*background:\s*var\(--app-page-color,\s*#F2F2F2\)/s);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\]\s*\{[^}]*--product-mobile-header-top-offset:\s*max\(20px, env\(safe-area-inset-top\)\)/s);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\] body,[\s\S]*html\[data-browser-surface="safari26"\] body,[\s\S]*html\[data-browser-surface="safari18"\] body\s*\{[^}]*background:\s*var\(--app-page-color,\s*#F2F2F2\)/s);
    assert.doesNotMatch(globalStylesSource, /html\[data-browser-surface="pwa"\] \.appPageShell\s*\{[^}]*min-height:\s*calc\(100dvh - env\(safe-area-inset-bottom\)\)/s);
    assert.doesNotMatch(globalStylesSource, /--cart-action-bar-bottom:\s*40px/);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\],[\s\S]*html\[data-browser-surface="safari26"\],[\s\S]*--cart-action-bar-bottom:\s*20px/s);
    assert.doesNotMatch(appEnvironmentSource, /window\.visualViewport|--app-visual-viewport-bottom-offset/);
    assert.match(globalStylesSource, /\.appSafariTopBar/);
    assert.doesNotMatch(globalStylesSource, /appSafariBottomBar/);
    assert.match(globalStylesSource, /\.appSafariTopBar\s*\{[^}]*z-index:\s*81/s);
    assert.match(globalStylesSource, /html\[data-browser-surface="safari26"\]\[data-app-page="catalog"\] \.appSafariTopBar/);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\]\[data-app-page="catalog"\] \.appSafariTopBar,[\s\S]*html\[data-browser-surface="safari18"\]\[data-app-page="product"\] \.appSafariTopBar\s*\{[^}]*display:\s*block/s);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\]\[data-app-page="catalog"\] \.appSafariTopBar,[\s\S]*background:\s*var\(--catalog-header-gradient\)[^}]*background-position:\s*center calc\(max\(20px, env\(safe-area-inset-top\)\) - 75px\)/s);
    assert.doesNotMatch(appEnvironmentSource, /className="appSafariBottomBar"/);
    assert.match(headerStylesSource, /\.backdrop\s*\{[^}]*z-index:\s*80/s);
});

test("mobile footer reserves scroll space while the cart action bar is rendered", () => {
    assert.match(footerSource, /className="site-footer /);
    assert.match(globalStylesSource, /@media\s*\(max-width:\s*1023px\)\s*\{[\s\S]*body:has\(\.cart-action-bar-shell\) \.site-footer\s*\{[\s\S]*padding-bottom:\s*clamp\(116px,\s*31vw,\s*205px\)/s);
    assert.doesNotMatch(globalStylesSource, /body\s*\{[^}]*padding-bottom:\s*clamp\(116px,\s*31vw,\s*205px\)/s);
});

test("catalog and product share the adaptive header backdrop through the top safe area", () => {
    assert.doesNotMatch(appEnvironmentSource, /appPwaCatalogTopBackdrop/);
    assert.doesNotMatch(globalStylesSource, /appPwaCatalogTopBackdrop/);
    assert.doesNotMatch(globalStylesSource, /catalogSafariTop/);
    assert.match(appEnvironmentSource, /page:\s*"catalog"[\s\S]*topColor:\s*"#F2F2F2"/);
    assert.match(appEnvironmentSource, /page:\s*"product"[\s\S]*topColor:\s*"#F2F2F2"/);
    assert.doesNotMatch(productPageSource, /catalogSafariTop|appSafariTopBar/);
    assert.match(globalStylesSource, /html\[data-browser-surface="safari26"\]\[data-app-page="catalog"\] \.appSafariTopBar/);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\]\[data-app-page="catalog"\] \.appSafariTopBar/);
    assert.match(globalStylesSource, /@media \(display-mode:\s*standalone\)\s*\{[\s\S]*\.appSafariTopBar\[data-app-top-page="catalog"\],[\s\S]*\.appSafariTopBar\[data-app-top-page="product"\][\s\S]*display:\s*block/s);
    assert.match(globalStylesSource, /@media \(display-mode:\s*standalone\)\s*\{[\s\S]*\.appSafariTopBar\[data-app-top-page="catalog"\],[\s\S]*background:\s*var\(--catalog-header-gradient\)[^}]*background-position:\s*center calc\(max\(20px, env\(safe-area-inset-top\)\) - 75px\)/s);
    assert.match(appEnvironmentSource, /data-app-top-page=\{pageChrome\.page\}/);
    assert.doesNotMatch(globalStylesSource, /html:not\(\[data-app-page\]\) \.appSafariTopBar/);
    assert.doesNotMatch(globalStylesSource, /\.appSafariBottomBar/);
    assert.match(headerStylesSource, /\.backdrop\s*\{[^}]*height:\s*var\(--catalog-header-gradient-height\)/s);
    assert.match(headerStylesSource, /\.backdrop\s*\{[^}]*background:\s*var\(--catalog-header-gradient\)/s);
    assert.match(headerStylesSource, /\.backdrop\s*\{[^}]*z-index:\s*80/s);
    assert.match(headerStylesSource, /\.backdrop\s*\{[^}]*top:\s*-55px/s);
    assert.match(globalStylesSource, /--catalog-header-gradient:[\s\S]*var\(--app-top-color, #F2F2F2\) 0%[\s\S]*#F2F2F2 56%[\s\S]*rgb\(242 242 242 \/ 54%\) 82%[\s\S]*rgb\(242 242 242 \/ 0%\) 100%/s);
    assert.match(headerStylesSource, /\.backdrop\s*\{[^}]*transform:\s*translate3d\(0,\s*0,\s*0\)[^}]*will-change:\s*transform/s);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\]\[data-app-page="constructor"\] \.constructorSafariTop/s);
});

test("app disables pull down reload gestures everywhere", () => {
    assert.doesNotMatch(appEnvironmentSource, /PWA_PULL_REFRESH_DISTANCE/);
    assert.doesNotMatch(appEnvironmentSource, /PWA_REFRESH_SPLASH_SKIP_KEY/);
    assert.doesNotMatch(appEnvironmentSource, /isPullRefreshVisible/);
    assert.doesNotMatch(appEnvironmentSource, /pullStartY|pullDistance|hasReloaded/);
    assert.doesNotMatch(appEnvironmentSource, /window\.location\.reload/);
    assert.doesNotMatch(appEnvironmentSource, /sessionStorage\.setItem/);
    assert.doesNotMatch(appEnvironmentSource, /window\.addEventListener\("touch(?:start|move|end|cancel)"/);
    assert.doesNotMatch(appEnvironmentSource, /appPullRefreshIndicator|ОБНОВЛЕНИЕ/);
    assert.match(globalStylesSource, /html,\s*body\s*\{[^}]*overscroll-behavior-y:\s*none/s);
    assert.doesNotMatch(globalStylesSource, /appPullRefreshIndicator/);
});

test("product page uses the shared top substrate in PWA and Safari", () => {
    assert.doesNotMatch(productPageSource, /catalogSafariTop|appSafariTopBar/);
    assert.match(globalStylesSource, /html\[data-browser-surface="safari26"\]\[data-app-page="product"\] \.appSafariTopBar/);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\]\[data-app-page="product"\] \.appSafariTopBar/);
    assert.doesNotMatch(globalStylesSource, /html\[data-browser-surface="safari26"\]\[data-app-page="product"\] \.catalogSafariTop/);
    assert.doesNotMatch(globalStylesSource, /html\[data-browser-surface="pwa"\]\[data-app-page="product"\] \.catalogSafariTop/);
});

test("pwa manifest exposes installable icons for launchers and apple devices", () => {
    assert.match(manifestSource, /background_color:\s*"#F2F2F2"/);
    assert.match(manifestSource, /theme_color:\s*"#F2F2F2"/);
    assert.match(layoutSource, /manifest:\s*"\/manifest\.webmanifest"/);
    assert.match(layoutSource, /icon:\s*"\/favicon\.ico"/);
    assert.match(layoutSource, /apple:\s*"\/apple-touch-icon\.png"/);

    assert.match(manifestSource, /src:\s*"\/pwa-icon-192\.png"[\s\S]*sizes:\s*"192x192"[\s\S]*type:\s*"image\/png"/);
    assert.match(manifestSource, /src:\s*"\/pwa-icon-512\.png"[\s\S]*sizes:\s*"512x512"[\s\S]*type:\s*"image\/png"/);
    assert.match(manifestSource, /purpose:\s*"any"/);
    assert.match(manifestSource, /purpose:\s*"maskable"/);
});

test("catalog and product header backdrop starts fifty five pixels above the viewport", () => {
    assert.match(headerStylesSource, /\.backdrop\s*\{[^}]*top:\s*-55px/s);
    assert.doesNotMatch(headerStylesSource, /\.backdrop\s*\{[^}]*top:\s*0/s);
    assert.match(headerStylesSource, /height:\s*var\(--catalog-header-gradient-height\)/);
    assert.match(headerStylesSource, /\.fixed\s*\{[^}]*transform:\s*translate3d\(0,\s*0,\s*0\)[^}]*will-change:\s*transform/s);
    assert.match(headerStylesSource, /:global\(html\[data-browser-surface="pwa"\]\) \.fixed\s*\{[^}]*top:\s*max\(var\(--header-top-offset,\s*20px\),\s*env\(safe-area-inset-top\)\)/s);
    assert.match(headerStylesSource, /@media \(display-mode:\s*standalone\)\s*\{[\s\S]*?\.fixed\s*\{[^}]*top:\s*max\(var\(--header-top-offset,\s*20px\),\s*env\(safe-area-inset-top\)\)/s);
    assert.match(headerStylesSource, /:global\(html\[data-browser-surface="pwa"\]\) \.backdrop\s*\{[^}]*top:\s*calc\(max\(20px,\s*env\(safe-area-inset-top\)\) - 75px\)/s);
    assert.match(headerStylesSource, /@media \(display-mode:\s*standalone\)\s*\{[\s\S]*?\.backdrop\s*\{[^}]*top:\s*calc\(max\(20px,\s*env\(safe-area-inset-top\)\) - 75px\)/s);
    assert.doesNotMatch(headerStylesSource, /top:\s*calc\(var\(--header-top-offset,\s*20px\) \+ env\(safe-area-inset-top\)\)/s);
});

test("constructor extends only its backdrop and overlays through the bottom safe area", () => {
    assert.doesNotMatch(headerStylesSource, /\.notFixed\.constructor/);
    assert.match(constructorSource, /constructorSafariTop/);
    assert.doesNotMatch(constructorSource, /constructorSafariBottom/);
    assert.match(constructorSource, /constructorVisibleViewport/);
    assert.match(globalStylesSource, /\.constructorSafariTop\s*\{[^}]*position:\s*fixed/s);
    assert.match(globalStylesSource, /\.constructorSafariTop\s*\{[^}]*z-index:\s*79/s);
    assert.match(globalStylesSource, /\.constructorSafariTop\s*\{[^}]*background:\s*#FFFFFF/s);
    assert.match(globalStylesSource, /\.constructorViewport\s*\{[^}]*calc\(100dvh \+ 160px\)/s);
    assert.doesNotMatch(globalStylesSource, /\.constructorViewport\s*\{[^}]*position:\s*fixed/s);
    assert.match(globalStylesSource, /\.constructorVisibleViewport\s*\{[^}]*height:\s*100dvh/s);
    assert.doesNotMatch(globalStylesSource, /app-viewport-bottom-extension|app-visual-viewport-bottom-offset/);
    assert.doesNotMatch(globalStylesSource, /constructorVisibleViewport::after/);
    assert.doesNotMatch(globalStylesSource, /\.constructorVisibleViewport\s*\{[^}]*app-viewport-bottom-extension/s);
    assert.doesNotMatch(globalStylesSource, /\.constructorVisibleViewport\s*\{[^}]*padding-top:\s*env\(safe-area-inset-top\)/s);
    assert.match(globalStylesSource, /--constructor-panel-bottom:\s*5px/);
    assert.doesNotMatch(globalStylesSource, /html\[data-browser-surface="pwa"\]\[data-app-page="constructor"\] \.constructorViewport\s*\{[^}]*--constructor-panel-bottom:\s*40px/s);
    assert.doesNotMatch(globalStylesSource, /--constructor-panel-bottom:\s*40px/);
    assert.doesNotMatch(globalStylesSource, /--constructor-panel-bottom:\s*0px/);
    assert.doesNotMatch(globalStylesSource, /data-app-page="constructor"\] \.viewportOverlayRoot,[\s\S]*bottom:\s*calc\(-1 \* env\(safe-area-inset-bottom\)\)/s);
    assert.doesNotMatch(globalStylesSource, /\.constructorSafariTop\s*\{[^}]*background-image:\s*url\('\/constructor_bg\.webp'\)/s);
    assert.doesNotMatch(globalStylesSource, /constructorSafariBottom/);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\]\[data-app-page="constructor"\] \.constructorSafariTop/s);
    assert.match(globalStylesSource, /html\[data-app-page="constructor"\]\[data-browser-surface="pwa"\] \.appSafariTopBar/);
    assert.match(globalStylesSource, /html\[data-app-page="constructor"\]\[data-browser-surface="safari26"\] \.appSafariTopBar/);
    assert.doesNotMatch(globalStylesSource, /\.appSafariBottomBar/);
    assert.doesNotMatch(globalStylesSource, /html\[data-app-page="constructor"\] \.appPageShell\s*\{[^}]*calc\(100dvh \+ 160px\)/s);
    assert.doesNotMatch(globalStylesSource, /html\[data-app-page="constructor"\] \.appPageShell\s*\{[^}]*padding-bottom:\s*calc\(var\(--app-page-bottom-offset,\s*0px\) \+ 160px\)/s);
    assert.match(globalStylesSource, /html\[data-app-page="constructor"\],\s*html\[data-app-page="constructor"\] body,\s*html\[data-app-page="constructor"\] \.appPageShell\s*\{[^}]*background-color:\s*#FFFFFF/s);
    assert.match(headerStylesSource, /:global\(html\[data-app-page="constructor"\]\[data-browser-surface="pwa"\]\) \.constructor\s*\{[^}]*padding-top:\s*env\(safe-area-inset-top\)/s);
    assert.match(headerStylesSource, /min-height:\s*calc\(clamp\(54px,\s*14\.6vw,\s*88px\) \+ env\(safe-area-inset-top\)\)/s);
    assert.doesNotMatch(headerStylesSource, /data-browser-surface="safari26"[^\n]*\.constructor/);
    assert.match(appEnvironmentSource, /metaThemeColor\.content = activeTopColor/);
    assert.match(constructorSource, /metaThemeColor|constructorOverlayActive|#FFFFFF/);
    assert.doesNotMatch(constructorSource, /document\.body\.style\.position = "fixed"/);
});

test("product mobile layout uses clamp sizing for larger phones", () => {
    assert.doesNotMatch(productPageSource, /pt-\[clamp\(70px,18\.92vw,121px\)\]/);
    assert.match(productPageSource, /className="pt-0 pb-\[100px\]/);
    assert.match(productPageSource, /w-\[clamp\(90px,24\.32vw,156px\)\]/);
    assert.match(productPageSource, /h-\[clamp\(300px,81\.08vw,520px\)\]/);
    assert.match(productPageSource, /w-\[clamp\(185px,50vw,320px\)\]/);
    assert.match(productPageSource, /h-\[clamp\(270px,72\.97vw,467px\)\]/);
    assert.match(productPageSource, /text-\[clamp\(9px,2\.43vw,16px\)\]/);
    assert.match(productPageSource, /fontSize:\s*'clamp\(14px,\s*3\.78vw,\s*24px\)'/);
});

test("product mobile second block and color selector use requested spacing", () => {
    assert.match(productPageSource, /className="flex w-full justify-between items-stretch gap-\[clamp\(25px,6\.76vw,43px\)\]"/);
    assert.doesNotMatch(productPageSource, /items-stretch gap-\[clamp\(25px,6\.76vw,43px\)\] mb-4/);
    assert.match(productPageSource, /className="mx-\[-20px\] px-\[5px\]"/);
    assert.match(productPageSource, /style=\{\{\s*paddingTop:\s*20,\s*paddingBottom:\s*20\s*\}\}/);
    assert.doesNotMatch(productPageSource, /className="mx-\[-20px\] px-\[5px\]"\s*style=\{\{[^}]*marginTop:\s*20/);
});

test("product page does not mount the legacy cart overlay over the cart action bar", () => {
    assert.doesNotMatch(productPageSource, /import \{\s*CartOverlay\s*\}/);
    assert.doesNotMatch(productPageSource, /<CartOverlay/);
    assert.doesNotMatch(productPageSource, /isCartOpen|setIsCartOpen/);
    assert.match(productPageSource, /visible=\{hasScrolled\}/);
    assert.doesNotMatch(productPageSource, /visible=\{hasScrolled && !isCartOpen\}/);
});

test("product mobile hero fills the first viewport and follows the PWA header safe area", () => {
    assert.match(productPageSource, /const PRODUCT_MOBILE_HEADER_TOP_OFFSET = 'var\(--product-mobile-header-top-offset, 20px\)'/);
    assert.match(productPageSource, /const PRODUCT_MOBILE_HEADER_HEIGHT = 'clamp\(38px,\s*8\.92vw,\s*57px\)'/);
    assert.match(productPageSource, /const PRODUCT_MOBILE_HEADER_FOOTPRINT = `calc\(\$\{PRODUCT_MOBILE_HEADER_TOP_OFFSET\} \+ \$\{PRODUCT_MOBILE_HEADER_HEIGHT\}\)`/);
    assert.match(productPageSource, /const PRODUCT_MOBILE_HERO_GAP = 'clamp\(24px,\s*9\.73vw,\s*36px\)'/);
    assert.match(productPageSource, /const PRODUCT_MOBILE_HERO_TOP_COMPENSATION = 'clamp\(4px,\s*1\.08vw,\s*4px\)'/);
    assert.match(productPageSource, /const PRODUCT_MOBILE_FIRST_BLOCK_TOP_OFFSET = 'clamp\(10px,\s*2\.7vw,\s*17px\)'/);
    assert.match(productPageSource, /product-mobile-hero flex min-h-\[100dvh\] w-full flex-col justify-between gap-\[clamp\(24px,9\.73vw,36px\)\]/);
    assert.doesNotMatch(productPageSource, /product-mobile-hero flex h-\[100dvh\]/);
    assert.match(productPageSource, /paddingTop:\s*`calc\(\$\{PRODUCT_MOBILE_HEADER_FOOTPRINT\} \+ \$\{PRODUCT_MOBILE_HERO_GAP\} \+ \$\{PRODUCT_MOBILE_HERO_TOP_COMPENSATION\} \+ \$\{PRODUCT_MOBILE_FIRST_BLOCK_TOP_OFFSET\}\)`/);
    assert.match(productPageSource, /top:\s*`calc\(clamp\(70px, 18\.92vw, 121px\) \+ \$\{PRODUCT_MOBILE_HEADER_TOP_OFFSET\} - 18px\)`/);
    assert.match(productPageSource, /boxSizing:\s*'border-box'/);
    assert.match(productPageSource, /className="flex flex-col lg:hidden w-full font-manrope relative"/);
    assert.doesNotMatch(productPageSource, /className="flex flex-col lg:hidden w-full font-manrope relative pb-10"/);
    assert.doesNotMatch(productPageSource, /product-mobile-hero[^"\n]*justify-start/);
    assert.doesNotMatch(productPageSource, /marginTop:\s*`calc\(\$\{PRODUCT_MOBILE_HEADER_FOOTPRINT\} \* -1\)`/);
    assert.doesNotMatch(productPageSource, /PRODUCT_MOBILE_HERO_MIN_HEIGHT|useIsomorphicLayoutEffect|productMobileHeroMinHeight|productMobileHeroTopPadding/);
    assert.doesNotMatch(productPageSource, /document\.querySelector\('header'\)\?\.getBoundingClientRect\(\)\.bottom/);
    assert.doesNotMatch(productPageSource, /min-h-\[calc\(100dvh-clamp\(/);
});

test("constructor owns only its overlay chrome state, not a separate bottom bar", () => {
    assert.doesNotMatch(constructorSource, /document\.body\.style\.backgroundColor/);
    assert.match(constructorSource, /constructorSafariTop/);
    assert.doesNotMatch(constructorSource, /constructorSafariBottom/);
    assert.match(globalStylesSource, /html\[data-app-page="constructor"\]\[data-browser-surface="pwa"\] \.appSafariTopBar/);
    assert.doesNotMatch(globalStylesSource, /app-viewport-bottom-extension|app-visual-viewport-bottom-offset/);
    assert.doesNotMatch(globalStylesSource, /constructorVisibleViewport::after/);
    assert.match(globalStylesSource, /--constructor-panel-bottom:\s*5px/);
    assert.match(constructorSource, /constructorOverlayActive|#FFFFFF/);
    assert.doesNotMatch(globalStylesSource, /html\[data-browser-surface="pwa"\]\[data-app-page="constructor"\] \.viewportOverlayRoot/);
});
