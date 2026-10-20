import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const layoutSource = fs.readFileSync(path.join(root, "app", "layout.tsx"), "utf8");
const globalStylesSource = fs.readFileSync(path.join(root, "app", "globals.css"), "utf8");
const appEnvironmentSource = [
    path.join(root, "providers", "AppEnvironmentProvider.tsx"),
    path.join(root, "lib", "browser", "utils", "pageChrome.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const headerSource = fs.readFileSync(path.join(root, "components", "layout", "Header.tsx"), "utf8");
const adaptiveHeaderSource = [
    path.join(root, "components", "layout", "AdaptiveHeader.tsx"),
    path.join(root, "hooks", "navigation", "useAdaptiveHeaderBehavior.ts"),
    path.join(root, "lib", "navigation", "data.ts"),
    path.join(root, "lib", "navigation", "types.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const adaptiveHeaderStyles = fs.readFileSync(path.join(root, "components", "layout", "AdaptiveHeader.module.css"), "utf8");
const constructorSource = [
    path.join(root, "components", "constructor", "ConstructorPage.tsx"),
    path.join(root, "components", "constructor", "ConstructorWorkspace.tsx"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const cartStoreSource = fs.readFileSync(path.join(root, "store", "cartStore.ts"), "utf8");

test("cart store keeps one active item and removes items when quantity reaches zero", () => {
    assert.match(cartStoreSource, /activeItemId:\s*string \| null/);
    assert.match(cartStoreSource, /setActiveItemId:\s*\(id:\s*string \| null\) => void/);
    assert.match(cartStoreSource, /updateItem:\s*\(id:\s*string,\s*item:\s*Omit<CartItem,\s*'id'>\) => void/);
    assert.match(cartStoreSource, /activeItemId:\s*null/);
    assert.match(cartStoreSource, /activeItemId:\s*id/);
    assert.match(cartStoreSource, /if \(existingItem\)[\s\S]*return \{[\s\S]*isCartOpen:\s*false,[\s\S]*activeItemId:\s*id/);
    assert.match(cartStoreSource, /const nextItems = \[\.\.\.state\.items, \{ \.\.\.newItem, id \}\];[\s\S]*return \{[\s\S]*isCartOpen:\s*false,[\s\S]*activeItemId:\s*id/);
    assert.match(cartStoreSource, /newQuantity <= 0/);
    assert.match(cartStoreSource, /nextItems\[nextItems\.length - 1\]\?\.id \|\| null/);
    assert.doesNotMatch(cartStoreSource, /Math\.max\(1,\s*newQuantity\)/);
});

test("PWA and Safari paint only the top safe area", () => {
    assert.match(appEnvironmentSource, /page:\s*"catalog"[\s\S]*bottomOffset:\s*"0px"/);
    assert.match(layoutSource, /themeColor:\s*"#F2F2F2"/);
    assert.doesNotMatch(globalStylesSource, /catalogSafariTop/);
    assert.doesNotMatch(globalStylesSource, /html\[data-browser-surface="pwa"\]\[data-app-page="product"\] \.catalogSafariTop/);
    assert.doesNotMatch(globalStylesSource, /html\[data-browser-surface="safari26"\]\[data-app-page="product"\] \.catalogSafariTop/);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\]\[data-app-page="product"\] \.appSafariTopBar/);
    assert.match(globalStylesSource, /html\[data-browser-surface="safari26"\]\[data-app-page="product"\] \.appSafariTopBar/);
    assert.match(globalStylesSource, /\.appSafariTopBar\s*\{[^}]*height:\s*max\(10px, env\(safe-area-inset-top\)\)[^}]*background:\s*var\(--app-top-color, #F2F2F2\)/s);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\]\[data-app-page="product"\] \.appSafariTopBar,[\s\S]*html\[data-browser-surface="safari18"\]\[data-app-page="product"\] \.appSafariTopBar\s*\{[^}]*background:\s*var\(--catalog-header-gradient\)[^}]*background-position:\s*center calc\(max\(20px, env\(safe-area-inset-top\)\) - 75px\)/s);
    assert.doesNotMatch(globalStylesSource, /appSafariBottomBar/);
    assert.doesNotMatch(appEnvironmentSource, /className="appSafariBottomBar"/);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\] body,[\s\S]*html\[data-browser-surface="safari26"\] body,[\s\S]*background:\s*var\(--app-page-color/s);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\],[\s\S]*html\[data-browser-surface="safari26"\],[\s\S]*background:\s*var\(--app-page-color, #F2F2F2\)/s);
    assert.doesNotMatch(layoutSource, /<meta name="theme-color" content="#FBFBFB" \/>/);
});

test("shared header and constructor retain their adaptive layout", () => {
    assert.match(headerSource, /<AdaptiveHeader/);
    assert.doesNotMatch(headerSource, /const isProductPage = pathname\?\.startsWith\("\/product"\)/);
    assert.doesNotMatch(headerSource, /shouldShowCatalogHeaderBackdrop/);
    assert.match(headerSource, /withBackdrop/);
    assert.match(headerSource, /\bfixed\b/);
    assert.doesNotMatch(headerSource, /fixed=\{!isProductPage\}/);
    assert.match(headerSource, /topOffset=\{20\}/);
    assert.match(adaptiveHeaderSource, /name="size-filter"/);
    assert.match(adaptiveHeaderSource, /styles\.backdropInline/);
    assert.match(adaptiveHeaderSource, /fixed \? styles\.fixed : styles\.notFixed/);
    assert.match(adaptiveHeaderStyles, /clamp\(34px,\s*8\.92vw,\s*57px\)/);
    assert.match(adaptiveHeaderStyles, /\.notFixed\s*\{[^}]*margin-top:\s*var\(--header-top-offset,\s*20px\)/s);
    assert.match(adaptiveHeaderStyles, /\.backdropInline\s*\{[^}]*position:\s*absolute/s);
    assert.match(adaptiveHeaderSource, /title = "Garment Buro"/);
    assert.match(adaptiveHeaderSource, /subtitle = "my collection"/);
    assert.match(adaptiveHeaderStyles, /--header-brand-gap:\s*7px/);
    assert.match(adaptiveHeaderStyles, /--header-text-gap:\s*0px/);
    assert.match(adaptiveHeaderStyles, /height:\s*var\(--catalog-header-gradient-height\)/);
    assert.match(adaptiveHeaderStyles, /background:\s*var\(--catalog-header-gradient\)/);
    assert.match(adaptiveHeaderStyles, /\.backdrop\s*\{[^}]*top:\s*-55px/s);
    assert.match(globalStylesSource, /--catalog-header-gradient:[\s\S]*var\(--app-top-color, #F2F2F2\) 0%[\s\S]*#F2F2F2 56%[\s\S]*rgb\(242 242 242 \/ 54%\) 82%[\s\S]*rgb\(242 242 242 \/ 0%\) 100%/);
    assert.match(adaptiveHeaderStyles, /transform:\s*translate3d\(0,\s*0,\s*0\)/);
    assert.match(adaptiveHeaderStyles, /\.fixed\s*\{[^}]*transform:\s*translate3d\(0,\s*0,\s*0\)[^}]*will-change:\s*transform/s);
    assert.match(adaptiveHeaderSource, /data-adaptive-header-backdrop/);
    assert.doesNotMatch(headerSource, /mobile-header-blur/);
    assert.doesNotMatch(layoutSource, /<AnimatedLogo/);
    assert.doesNotMatch(layoutSource, /<ScrollToTop/);
    assert.match(constructorSource, /variant="constructor"/);
    assert.match(constructorSource, /sizeLabel=\{selectedSize \? `Размер: \$\{selectedSize\}` : "Цвет\/Размер"\}/);
});
