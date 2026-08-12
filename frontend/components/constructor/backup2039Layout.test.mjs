import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (...parts) => fs.readFileSync(path.join(root, ...parts), "utf8");

const layoutSource = read("app", "layout.tsx");
const globalStylesSource = read("app", "globals.css");
const splashSource = [
    read("components", "shared", "SplashScreen.tsx"),
    read("hooks", "browser", "useSplashController.ts"),
].join("\n");
const environmentSource = [
    read("providers", "AppEnvironmentProvider.tsx"),
    read("lib", "browser", "utils", "pageChrome.ts"),
].join("\n");
const constructorSource = [
    read("components", "constructor", "ConstructorWorkspace.tsx"),
    read("components", "constructor", "ConstructorInstructionOverlay.tsx"),
    read("components", "constructor", "SizeFitModal.tsx"),
    read("components", "cart", "CartActionBar.tsx"),
    read("hooks", "constructor", "useConstructorPageEnvironment.ts"),
    read("hooks", "constructor", "useConstructorPageController.ts"),
    read("lib", "cart", "constants.ts"),
    read("lib", "constructor", "constants.ts"),
].join("\n");

test("the 15 July 20:39 splash waits for logo_anim readiness after hydration", () => {
    assert.match(splashSource, /const \[show, setShow\] = useState\(false\)/);
    assert.match(splashSource, /const openTimer = window\.setTimeout\(\(\) => setShow\(true\), 0\)/);
    assert.match(splashSource, /if \(isHiddenRoute \|\| !show\) return null/);
    assert.match(splashSource, /opacity: logoReady \? 1 : 0/);
    assert.match(splashSource, /src="\/logo_anim\.mp4"/);
    assert.match(splashSource, /onCanPlayThrough=\{tryPlayLogo\}/);
    assert.match(splashSource, /onPlaying=\{handleLogoPlaying\}/);
    assert.doesNotMatch(splashSource, /pwa-icon-source|poster=|splashBootstrapScript/);
    assert.doesNotMatch(layoutSource, /data-p2o-splash|suppressHydrationWarning|black-translucent/);
});

test("the constructor uses the restored 20:39 viewport and lower panel geometry", () => {
    assert.match(globalStylesSource, /\.constructorViewport\s*\{[^}]*height:\s*calc\(100dvh \+ 160px\)/s);
    assert.match(globalStylesSource, /\.constructorVisibleViewport\s*\{[^}]*height:\s*100dvh/s);
    assert.match(globalStylesSource, /--constructor-panel-bottom:\s*5px/);
    assert.doesNotMatch(globalStylesSource, /--app-viewport-bottom-extension|--app-visual-viewport-bottom-offset/);
    assert.match(constructorSource, /const panelBottomForCanvas = 10/);
    assert.match(constructorSource, /CART_ACTION_EXPANDED_BOTTOM_LIFT = 10/);
    assert.match(constructorSource, /paddingTop: "max\(52px, calc\(env\(safe-area-inset-top\) \+ 42px\)\)"/);
    assert.doesNotMatch(constructorSource, /document\.body\.style\.position = "fixed"/);
});

test("the constructor overlay repaints the safe area on two animation frames", () => {
    assert.match(environmentSource, /page:\s*"constructor"[\s\S]*topColor:\s*"#FFFFFF"[\s\S]*pageColor:\s*"#FFFFFF"/);
    assert.match(constructorSource, /html\.dataset\.constructorOverlayActive = "true"/);
    assert.match(constructorSource, /metaThemeColor\.content = "#FFFFFF"/);
    assert.match(constructorSource, /requestAnimationFrame\(\(\) => \{[\s\S]*requestAnimationFrame\(applyOverlayChrome\)/);
    assert.match(constructorSource, /setTimeout\(applyOverlayChrome, 120\)/);
    assert.match(globalStylesSource, /data-constructor-overlay-active="true"[\s\S]*background-color:\s*#FFFFFF/s);
    assert.match(globalStylesSource, /data-constructor-overlay-active="true"[\s\S]*display:\s*block !important;[\s\S]*z-index:\s*2147483644/s);
    assert.match(environmentSource, /MutationObserver\(syncPageChrome\)/);
    assert.match(environmentSource, /data-app-top-page=\{pageChrome\.page\}/);
});

test("the size modal fits its controls without an internal scroll container", () => {
    assert.doesNotMatch(constructorSource, /constructorSizeModal[^\n]*h-\[min\(780px,calc\(100dvh-10px\)\)\]/);
    assert.match(constructorSource, /constructorSizeModal[^\n]*overflow-hidden/);
    assert.doesNotMatch(constructorSource, /constructorSizeModal[^\n]*overflow-y-auto/);
    assert.match(constructorSource, /h-\[clamp\(210px,32dvh,300px\)\]/);
});
