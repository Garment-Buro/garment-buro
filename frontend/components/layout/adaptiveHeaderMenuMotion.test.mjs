import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const headerSource = fs.readFileSync(path.join(root, "components", "layout", "Header.tsx"), "utf8");
const adaptiveHeaderSource = [
    path.join(root, "components", "layout", "AdaptiveHeader.tsx"),
    path.join(root, "hooks", "navigation", "useAdaptiveHeaderBehavior.ts"),
    path.join(root, "lib", "navigation", "data.ts"),
    path.join(root, "lib", "navigation", "types.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const adaptiveHeaderStyles = fs.readFileSync(path.join(root, "components", "layout", "AdaptiveHeader.module.css"), "utf8");

test("catalog burger opens the adaptive category menu instead of auth", () => {
    assert.doesNotMatch(headerSource, /AuthPopup/);
    assert.doesNotMatch(headerSource, /setIsAuthPopupOpen/);
    assert.match(adaptiveHeaderSource, /CATEGORY_MENU_ITEMS/);
    assert.match(adaptiveHeaderSource, /id="adaptive-category-menu"/);
    assert.match(adaptiveHeaderSource, /aria-controls="adaptive-category-menu"/);
});

test("adaptive category menu is portaled above product-page stacking contexts", () => {
    assert.match(adaptiveHeaderSource, /const categoryMenuPortal = !isConstructor && categoryMenu && typeof document !== "undefined"/);
    assert.match(adaptiveHeaderSource, /createPortal\(categoryMenu, document\.body\)/);
    assert.doesNotMatch(adaptiveHeaderSource, /\{categoryMenu\}\s*\n\s*\{isConstructor/);
});

test("adaptive category menu closes on route changes and outside presses", () => {
    assert.match(adaptiveHeaderSource, /const pathname = usePathname\(\)/);
    assert.match(adaptiveHeaderSource, /previousPathnameRef\.current === pathname/);
    assert.match(adaptiveHeaderSource, /previousPathnameRef\.current = pathname;[\s\S]*window\.requestAnimationFrame\(closeCategoryMenu\)/);
    assert.match(adaptiveHeaderSource, /window\.cancelAnimationFrame\(animationFrameId\)/);
    assert.match(adaptiveHeaderSource, /document\.addEventListener\(['"]pointerdown['"], handlePointerDown, true\)/);
    assert.match(adaptiveHeaderSource, /document\.removeEventListener\(['"]pointerdown['"], handlePointerDown, true\)/);
    assert.match(adaptiveHeaderSource, /headerRef\.current\?\.contains\(target\) \|\| categoryMenuRef\.current\?\.contains\(target\)/);
});

test("adaptive category menu closes from links and selected items", () => {
    assert.match(adaptiveHeaderSource, /onClickCapture=\{handleMenuClickCapture\}/);
    assert.match(adaptiveHeaderSource, /target\.closest\(['"]a['"]\)/);
    assert.match(adaptiveHeaderSource, /data-menu-selection/);
    assert.match(adaptiveHeaderSource, /onClick=\{handleMenuSelection\}/);
    assert.match(adaptiveHeaderSource, /onClick=\{closeCategoryMenu\}/);
    assert.match(adaptiveHeaderSource, /<div\s+className=\{\[styles\.categoryItem/);
    assert.doesNotMatch(adaptiveHeaderSource, /<button\s+type="button"\s+className=\{\[styles\.categoryItem/);
});

test("adaptive category menu links to the Light Running landing below categories", () => {
    assert.match(adaptiveHeaderSource, /<NextLink[\s\S]*?href="\/light-running"[\s\S]*?className=\{styles\.lightRunningLink\}[\s\S]*?Light running[\s\S]*?<\/NextLink>/);
    assert.match(adaptiveHeaderStyles, /\.lightRunningLink\s*\{[^}]*height:\s*50px[^}]*justify-content:\s*center[^}]*border-radius:\s*15px[^}]*linear-gradient\(135deg[^}]*color:\s*#FFF[^}]*font-size:\s*15px[^}]*font-weight:\s*700/s);
});

test("adaptive category menu uses the requested grey glass background", () => {
    assert.match(adaptiveHeaderSource, /background:\s*"rgb\(227 227 227 \/ 85%\)"/);
    assert.match(adaptiveHeaderStyles, /\.categoryMenu\s*\{[^}]*background:\s*rgb\(227 227 227 \/ 85%\)/s);
});

test("adaptive category menu fades in and remains mounted during fade out", () => {
    assert.match(adaptiveHeaderSource, /const \[isCategoryMenuMounted,\s*setIsCategoryMenuMounted\] = useState\(false\)/);
    assert.match(adaptiveHeaderSource, /setIsCategoryMenuOpen\(false\)[\s\S]*window\.setTimeout\(\(\) => \{\s*setIsCategoryMenuMounted\(false\)/);
    assert.match(adaptiveHeaderSource, /setIsCategoryMenuMounted\(true\)[\s\S]*window\.requestAnimationFrame\(\(\) => \{\s*setIsCategoryMenuOpen\(true\)/);
    assert.match(adaptiveHeaderSource, /const CATEGORY_MENU_FADE_OUT_MS = 360/);
    assert.match(adaptiveHeaderSource, /setCategoryMenuTop\(headerRect\.bottom \+ 8\)[\s\S]*setIsCategoryMenuMounted\(true\)/);
    assert.match(adaptiveHeaderSource, /window\.requestAnimationFrame\(\(\) => \{[\s\S]*window\.requestAnimationFrame\(\(\) => \{\s*setIsCategoryMenuOpen\(true\)/);
    assert.match(adaptiveHeaderStyles, /\.categoryMenu\s*\{[^}]*transition:\s*opacity 420ms cubic-bezier\(0\.4, 0, 0\.2, 1\)/s);
    assert.match(adaptiveHeaderStyles, /\.categoryMenuHidden\s*\{[^}]*transition-duration:\s*360ms/s);
    assert.doesNotMatch(adaptiveHeaderStyles, /translate3d\(-50%, -6px, 0\)/);
    assert.match(adaptiveHeaderStyles, /\.categoryMenuVisible\s*\{[^}]*opacity:\s*1/s);
    assert.match(adaptiveHeaderStyles, /\.categoryMenuHidden\s*\{[^}]*opacity:\s*0/s);
});

test("burger keeps a compact icon inside a larger tap target", () => {
    assert.match(adaptiveHeaderStyles, /--header-burger-width:\s*15px/);
    assert.match(adaptiveHeaderStyles, /--header-burger-hit-size:\s*44px/);
    assert.match(adaptiveHeaderStyles, /\.burgerButton\s*\{[^}]*width:\s*var\(--header-burger-hit-size\)[^}]*height:\s*var\(--header-burger-hit-size\)/s);
    assert.match(adaptiveHeaderStyles, /\.burgerIcon\s*\{[^}]*width:\s*var\(--header-burger-width\)[^}]*gap:\s*var\(--header-burger-gap\)/s);
    assert.match(adaptiveHeaderSource, /<span className=\{styles\.burgerIcon\} aria-hidden="true">/);
});

test("adaptive category menu aligns collapsed subtitles and expanded grids to the end", () => {
    assert.match(adaptiveHeaderStyles, /\.categoryContentSlot\s*\{[^}]*justify-items:\s*end/s);
    assert.doesNotMatch(adaptiveHeaderStyles, /\.categoryContentSlot\s*\{[^}]*justify-items:\s*start/s);
});

test("category titles keep identical geometry while a category expands", () => {
    assert.match(adaptiveHeaderStyles, /\.categoryTitle\s*\{[^}]*height:\s*44px[^}]*min-height:\s*44px[^}]*padding:\s*0[^}]*line-height:\s*20px/s);
    assert.match(adaptiveHeaderStyles, /\.categoryTitle,\s*\.categorySubtitle,\s*\.categoryLinkLabel\s*\{[^}]*appearance:\s*none[^}]*border:\s*0[^}]*padding:\s*0[^}]*background:\s*transparent/s);
    assert.doesNotMatch(adaptiveHeaderStyles, /\.categoryItemExpanded \.categoryTitle\s*\{/);
    assert.doesNotMatch(adaptiveHeaderStyles, /transition:\s*padding-top/);
});
