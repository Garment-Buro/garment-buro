import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const landingSource = [
    path.join(root, "components", "shared", "LandingPage.tsx"),
    path.join(root, "components", "catalog", "CatalogScreen.tsx"),
    path.join(root, "hooks", "catalog", "useCatalogPage.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const homeSource = [
    path.join(root, "app", "page.tsx"),
    path.join(root, "lib", "catalog", "data.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const publicCatalogSource = fs.readFileSync(path.join(root, "lib", "catalog", "public.ts"), "utf8");
const phantomBootstrapSource = fs.readFileSync(path.join(root, "components", "runtime", "PhantomUiBootstrap.tsx"), "utf8");
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
const mobileProductCardSource = [
    path.join(root, "components", "shared", "MobileProductCard.tsx"),
    path.join(root, "hooks", "catalog", "useMobileCatalogCardVideo.ts"),
    path.join(root, "hooks", "cart", "useCatalogCartItem.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const productCardSource = [
    path.join(root, "components", "shared", "ProductCard.tsx"),
    path.join(root, "hooks", "catalog", "useDesktopCatalogCardVideo.ts"),
    path.join(root, "hooks", "cart", "useCatalogCartItem.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const catalogQuantityControlSource = fs.readFileSync(path.join(root, "components", "shared", "CatalogQuantityControl.tsx"), "utf8");
const catalogQuantityControlStyles = fs.readFileSync(path.join(root, "components", "shared", "CatalogQuantityControl.module.css"), "utf8");
const videoFrameRevealSource = fs.readFileSync(path.join(root, "hooks", "media", "useVideoFrameReveal.ts"), "utf8");
const catalogVideoAutoplayPath = path.join(root, "store", "catalogVideoAutoplayStore.ts");
const catalogVideoAutoplaySource = fs.existsSync(catalogVideoAutoplayPath) ? fs.readFileSync(catalogVideoAutoplayPath, "utf8") : "";
const cartActionBarPath = path.join(root, "components", "cart", "CartActionBar.tsx");
const cartActionBarSource = fs.existsSync(cartActionBarPath) ? [
    cartActionBarPath,
    path.join(root, "components", "cart", "CartAddProductCard.tsx"),
    path.join(root, "components", "cart", "CartChoiceOption.tsx"),
    path.join(root, "components", "cart", "CartCheckoutSections.tsx"),
    path.join(root, "components", "cart", "CartExpandedContent.tsx"),
    path.join(root, "components", "cart", "CartGuestAuthPrompt.tsx"),
    path.join(root, "components", "cart", "CartItemDetailsPopup.tsx"),
    path.join(root, "components", "cart", "CartItemRow.tsx"),
    path.join(root, "components", "cart", "CartQuantityControl.tsx"),
    path.join(root, "lib", "cart", "actionTypes.ts"),
    path.join(root, "lib", "cart", "constants.ts"),
    path.join(root, "lib", "cart", "utils", "cartAction.ts"),
    path.join(root, "hooks", "cart", "useCartActionCheckout.ts"),
    path.join(root, "hooks", "cart", "useCartActionVisibility.ts"),
    path.join(root, "hooks", "cart", "useCartPanelGeometry.ts"),
    path.join(root, "hooks", "cart", "useCartActionBarController.ts"),
    path.join(root, "lib", "api", "orders.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n") : "";
const cartStoreSource = fs.readFileSync(path.join(root, "store", "cartStore.ts"), "utf8");
const productPageSource = [
    path.join(root, "components", "product", "ProductPageClient.tsx"),
    path.join(root, "components", "product", "ProductDesktopLayout.tsx"),
    path.join(root, "components", "product", "ProductMobileLayout.tsx"),
    path.join(root, "components", "product", "ProductModals.tsx"),
    path.join(root, "hooks", "product", "useProductPage.ts"),
    path.join(root, "lib", "products", "constants.ts"),
    path.join(root, "lib", "products", "utils", "product.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");

test("legacy catalog stays reusable internally while the public home is platform first", () => {
    assert.doesNotMatch(landingSource, /phantom-ui|LandingSkeleton/);
    assert.match(landingSource, /initialProducts/);
    assert.match(landingSource, /initialSettings/);
    assert.match(homeSource, /PlatformEntry/);
    assert.doesNotMatch(homeSource, /<LandingPage initialProducts=\{products\}/);
    assert.match(publicCatalogSource, /PUBLIC_CATALOG_ENABLED = false/);
    assert.match(phantomBootstrapSource, /if \(pathname === "\/"\) return/);
});

test("catalog uses the adaptive header and product cards use the new add button", () => {
    assert.match(headerSource, /<AdaptiveHeader/);
    assert.doesNotMatch(landingSource, /catalogSafariTop/);
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

    assert.match(mobileProductCardSource, /left:\s*'calc\(clamp\(16px,\s*3\.75vw,\s*24px\) \* -1\)'/);
    assert.doesNotMatch(mobileProductCardSource, /left-\[-15px\]/);
    assert.match(mobileProductCardSource, /top-1\/2/);
    assert.match(mobileProductCardSource, /w-\[32px\] h-\[42px\]/);
    assert.match(mobileProductCardSource, /width=\{16\}/);
    assert.match(mobileProductCardSource, /h-\[16px\] w-\[16px\]/);
    assert.match(catalogQuantityControlSource, /add_cart_catalog_plus\.svg/);
    assert.match(catalogQuantityControlSource, /h-\[34px\]/);
    assert.match(catalogQuantityControlSource, /style=\{\{ width: hasQuantity \? 76 : 34 \}\}/);
    assert.match(mobileProductCardSource, /mt-\[6px\]/);
    assert.match(mobileProductCardSource, /gap-\[10px\]/);
    assert.match(mobileProductCardSource, /flex-row items-center gap-\[3px\]/);
    assert.doesNotMatch(mobileProductCardSource, /border border-black\/10/);
    assert.match(productCardSource, /flex-row items-center gap-\[3px\]/);
    assert.doesNotMatch(productCardSource, /border border-black\/10/);
    assert.match(productCardSource, /left-\[-15px\]/);
    assert.match(productCardSource, /h-\[40px\] w-\[30px\]/);
    assert.match(productCardSource, /width=\{15\}/);
    assert.match(mobileProductCardSource, /clamp\(110px,24vw,154px\)/);

    assert.match(mobileProductCardSource, /if \(!videoSrc \|\| !shouldLoadVideo\) return/);
    assert.match(productCardSource, /if \(!videoSrc \|\| !shouldLoadNearViewport\) return/);
    assert.doesNotMatch(mobileProductCardSource, /if \(videoSrc\) \{\s*registerVideo/s);
    assert.doesNotMatch(productCardSource, /if \(videoSrc\) \{\s*registerVideo/s);
    assert.match(mobileProductCardSource, /useCatalogVideoAutoplay/);
    assert.match(productCardSource, /useCatalogVideoAutoplay/);
    assert.match(mobileProductCardSource, /isCatalogVideoActive/);
    assert.match(productCardSource, /isCatalogVideoActive/);
    assert.doesNotMatch(mobileProductCardSource, /autoPlay=\{actuallyLoadVideo\}/);
    assert.match(mobileProductCardSource, /preload=\{actuallyLoadVideo \? "auto" : "none"\}/);
    assert.match(mobileProductCardSource, /video\.muted = true/);
    assert.match(mobileProductCardSource, /currentVideo\.play\(\)/);
    assert.match(mobileProductCardSource, /onPlaying=\{handlePlaying\}/);
    assert.match(mobileProductCardSource, /handlePlaying:[\s\S]*revealVideoAfterFirstFrame\(\)/);
    assert.match(mobileProductCardSource, /onCanPlay=\{handleCanPlayThrough\}/);
    assert.match(mobileProductCardSource, /onLoadedData=\{handleCanPlayThrough\}/);
});

test("catalog add button becomes an inline quantity stepper", () => {
    assert.match(mobileProductCardSource, /useCatalogCartItem/);
    assert.match(productCardSource, /useCatalogCartItem/);
    assert.match(mobileProductCardSource, /items\.find\(\(item\) => item\.id === `\$\{productId\}__`\)/);
    assert.match(productCardSource, /items\.find\(\(item\) => item\.id === `\$\{productId\}__`\)/);
    assert.match(mobileProductCardSource, /<CatalogQuantityControl/);
    assert.match(productCardSource, /<CatalogQuantityControl/);
    assert.match(mobileProductCardSource, /updateQuantity\(cartItem\.id, cartItem\.quantity - 1\)/);
    assert.match(productCardSource, /updateQuantity\(cartItem\.id, cartItem\.quantity \+ 1\)/);
    assert.match(catalogQuantityControlSource, /const hasQuantity = quantity > 0/);
    assert.match(catalogQuantityControlSource, /catalog-quantity-stepper/);
    assert.match(catalogQuantityControlSource, /style=\{\{ width: hasQuantity \? 76 : 34 \}\}/);
    assert.match(catalogQuantityControlSource, /CatalogQuantityControl\.module\.css/);
    assert.match(catalogQuantityControlSource, /styles\.contentIn/);
    assert.match(catalogQuantityControlStyles, /width 320ms cubic-bezier\(0\.22, 1, 0\.36, 1\)/);
    assert.match(catalogQuantityControlStyles, /animation: catalogQuantityContentIn 240ms/);
    assert.match(catalogQuantityControlStyles, /prefers-reduced-motion: reduce/);
    assert.match(catalogQuantityControlSource, /aria-label="Уменьшить количество"/);
    assert.match(catalogQuantityControlSource, /aria-label="Увеличить количество"/);
    assert.match(catalogQuantityControlSource, /aria-live="polite"/);
    assert.match(catalogQuantityControlSource, /event\.preventDefault\(\)/);
    assert.match(catalogQuantityControlSource, /event\.stopPropagation\(\)/);
});

test("catalog videos wait for the upper product before playback", () => {
    assert.match(catalogVideoAutoplaySource, /CATALOG_VIDEO_DWELL_MS = 2000/);
    assert.match(catalogVideoAutoplaySource, /pickUpperCatalogCandidate/);
    assert.match(catalogVideoAutoplaySource, /setTimeout\(\(\) => \{/);
    assert.match(catalogVideoAutoplaySource, /clearTimeout\(dwellTimer\)/);
    assert.match(catalogVideoAutoplaySource, /window\.addEventListener\('scroll', measure/);
    assert.match(catalogVideoAutoplaySource, /window\.addEventListener\('resize', measure/);
    assert.match(catalogVideoAutoplaySource, /currentActiveVideoId === id/);

    assert.match(mobileProductCardSource, /useCatalogVideoAutoplay\(queueId,\s*containerRef,\s*Boolean\(videoSrc\)\)/);
    assert.match(mobileProductCardSource, /if \(!actuallyLoadVideo \|\| !videoSrc \|\| !isCatalogVideoActive\) return/);
    assert.match(mobileProductCardSource, /showVideo: Boolean\(videoSrc && hasPresentedFrame && isCatalogVideoActive\)/);
    assert.doesNotMatch(mobileProductCardSource, /setVideoPlayed/);
    assert.match(mobileProductCardSource, /poster=\{leftImage\}/);
    assert.match(mobileProductCardSource, /window\.addEventListener\('p2o_splash_done', startPlayback\)/);
    assert.match(mobileProductCardSource, /window\.addEventListener\('pageshow', startPlayback\)/);
    assert.match(mobileProductCardSource, /document\.addEventListener\('visibilitychange', handleVisibilityChange\)/);
    assert.match(mobileProductCardSource, /setVideoStatus\(queueId, 'error'\)/);
    assert.match(mobileProductCardSource, /onPause=\{handlePlaybackInterruption\}/);
    assert.match(mobileProductCardSource, /onWaiting=\{handlePlaybackInterruption\}/);
    assert.match(mobileProductCardSource, /if \(!isCatalogVideoActive\) videoRef\.current\?\.pause\(\)/);

    assert.match(productCardSource, /useCatalogVideoAutoplay\(queueId,\s*containerRef,\s*Boolean\(videoSrc\)\)/);
    assert.match(productCardSource, /if \(isCatalogVideoActive && videoReady\) playFromCurrentPosition\(\)/);
    assert.match(productCardSource, /!isCatalogVideoActive && !isHovered/);
    assert.match(productCardSource, /showVideo: Boolean\(videoSrc && isVideoPlaying && hasPlaybackStarted && hasPresentedFrame\)/);
    assert.match(productCardSource, /poster=\{videoPoster\}/);
    assert.match(productCardSource, /bg-\[#F2F2F2\]/);
    assert.match(productCardSource, /revealVideoAfterFirstFrame\(\)/);
    assert.match(productCardSource, /hideVideoUntilFirstFrame\(\)/);
    assert.match(productCardSource, /window\.addEventListener\('p2o_splash_done', playFromCurrentPosition\)/);
    assert.match(productCardSource, /window\.addEventListener\('pageshow', playFromCurrentPosition\)/);
    assert.match(videoFrameRevealSource, /requestVideoFrameCallback\(\(\) => \{/);
    assert.match(videoFrameRevealSource, /!video\.paused && video\.readyState >= HTMLMediaElement\.HAVE_CURRENT_DATA/);
    assert.match(videoFrameRevealSource, /window\.setTimeout\(\(\) => \{/);
});

test("mobile product page uses the revised product info, colors, and fixed cart CTA", () => {
    assert.doesNotMatch(productPageSource, /mobile_edit_icon\.png/);
    assert.doesNotMatch(productPageSource, /add_to_cart_button_bg\.png/);
    assert.doesNotMatch(productPageSource, /photoBlockRef/);
    assert.doesNotMatch(productPageSource, /isCtaFixed/);
    assert.doesNotMatch(productPageSource, /pt-\[clamp\(70px,18\.92vw,121px\)\]/);
    assert.match(productPageSource, /className="pt-0 pb-\[100px\]/);

    assert.match(productPageSource, /w-\[clamp\(185px,50vw,320px\)\] h-\[clamp\(270px,72\.97vw,467px\)\]/);
    assert.match(productPageSource, /justify-between items-stretch gap-\[clamp\(25px,6\.76vw,43px\)\]/);
    assert.match(productPageSource, /product-mobile-hero/);
    assert.doesNotMatch(productPageSource, /product-mobile-hero flex h-\[100dvh\]/);
    assert.match(productPageSource, /const PRODUCT_MOBILE_HEADER_HEIGHT = 'clamp\(38px, 8\.92vw, 57px\)'/);
    assert.match(productPageSource, /const PRODUCT_MOBILE_HEADER_TOP_OFFSET = 'var\(--product-mobile-header-top-offset, 20px\)'/);
    assert.match(productPageSource, /const PRODUCT_MOBILE_HERO_GAP = 'clamp\(24px, 9\.73vw, 36px\)'/);
    assert.match(productPageSource, /const PRODUCT_MOBILE_HERO_TOP_COMPENSATION = 'clamp\(4px, 1\.08vw, 4px\)'/);
    assert.match(productPageSource, /const PRODUCT_MOBILE_FIRST_BLOCK_TOP_OFFSET = 'clamp\(10px, 2\.7vw, 17px\)'/);
    assert.match(productPageSource, /paddingTop:\s*`calc\(\$\{PRODUCT_MOBILE_HEADER_FOOTPRINT\} \+ \$\{PRODUCT_MOBILE_HERO_GAP\} \+ \$\{PRODUCT_MOBILE_HERO_TOP_COMPENSATION\} \+ \$\{PRODUCT_MOBILE_FIRST_BLOCK_TOP_OFFSET\}\)`/);
    assert.match(productPageSource, /top:\s*`calc\(clamp\(70px, 18\.92vw, 121px\) \+ \$\{PRODUCT_MOBILE_HEADER_TOP_OFFSET\} - 18px\)`/);
    assert.match(productPageSource, /boxSizing:\s*'border-box'/);
    assert.match(productPageSource, /className="flex flex-col lg:hidden w-full font-manrope relative"/);
    assert.doesNotMatch(productPageSource, /className="flex flex-col lg:hidden w-full font-manrope relative pb-10"/);
    assert.match(productPageSource, /className="product-mobile-hero flex min-h-\[100dvh\] w-full flex-col justify-between gap-\[clamp\(24px,9\.73vw,36px\)\]"/);
    assert.match(productPageSource, /alt="Size Chart First"[\s\S]*?priority[\s\S]*?loading="eager"[\s\S]*?fetchPriority="high"[\s\S]*?sizes="\(max-width: 1023px\) 24vw, 156px"/);
    assert.match(productPageSource, /alt="Mobile First"[\s\S]*?priority[\s\S]*?loading="eager"[\s\S]*?fetchPriority="high"[\s\S]*?sizes="\(max-width: 1023px\) 50vw, 320px"/);
    assert.match(mobileProductCardSource, /w-\[32px\] h-\[42px\][\s\S]*?w-\[32px\] h-\[30px\][\s\S]*?width=\{16\} height=\{16\}/);
    assert.doesNotMatch(productPageSource, /marginTop:\s*`calc\(\$\{PRODUCT_MOBILE_HEADER_FOOTPRINT\} \* -1\)`/);
    assert.doesNotMatch(productPageSource, /productMobileHeroMinHeight|productMobileHeroTopPadding/);
    assert.doesNotMatch(productPageSource, /document\.querySelector\('header'\)\?\.getBoundingClientRect\(\)\.bottom/);
    assert.doesNotMatch(productPageSource, /flex w-full justify-between items-center mb-\[40px\]/);
    assert.match(productPageSource, /bg-\[#F2F2F2\]/);
    assert.doesNotMatch(productPageSource, /mb-\[40px\] mt-\[40px\]/);
    assert.match(productPageSource, /object-cover object-top/);
    assert.match(productPageSource, /objectPosition:\s*'top center'/);
    assert.match(productPageSource, /className="mt-\[30px\]"[\s\S]{0,300}color:\s*'#2D2D2D'/);
    assert.match(productPageSource, /className="pt-\[30px\]"[\s\S]{0,260}<ProductTitle title=\{product\.title\} \/>/);
    assert.match(productPageSource, /export const normalizeProductDescription = \(description: string\) => description[\s\S]*replace\(\/\[\\u2028\\u2029\]\\n\?\/g, '\\n'\)/);
    assert.match(productPageSource, /const normalizedProductDescription = product\?\.description[\s\S]{0,140}normalizeProductDescription\(product\.description\)/);
    assert.match(productPageSource, /whitespace-pre-wrap[\s\S]{0,160}\{normalizedProductDescription \|\|/);
    assert.match(productPageSource, /color:\s*'#2D2D2D'/);
    assert.match(productPageSource, /justify-between/);

    assert.match(productPageSource, /mx-\[-20px\]\s*px-\[5px\]/);
    assert.match(productPageSource, /className="mx-\[-20px\] px-\[5px\]"\s*style=\{\{ paddingTop: 20, paddingBottom: 20 \}\}/);
    assert.doesNotMatch(productPageSource, /className="mx-\[-20px\] px-\[5px\]"\s*style=\{\{ marginTop: 20/);
    assert.match(productPageSource, /className=\{`text-\[20px\][^`]*w-\[clamp\(40px,10\.81vw,69px\)\]/);
    assert.doesNotMatch(productPageSource, /text-\[clamp\(14px,3\.78vw,24px\)\]/);
    assert.doesNotMatch(productPageSource, /background:\s*'#FCFCF8'/);
    assert.match(productPageSource, /gap-\[10px\]/);

    assert.match(productPageSource, /<CartActionBar/);
    assert.match(productPageSource, /visible=\{hasScrolled\}/);
    assert.match(productPageSource, /items\.find\(item => item\.id === `\$\{product\.id\}_\$\{selectedSize\}_\$\{currentCartColor\}`\)/);
    assert.match(productPageSource, /currentProductCartItem/);
    assert.match(productPageSource, /usePreferredCartItemOnly/);
    assert.match(productPageSource, /export const getProductCartImage = \(product: ProductData\) =>/);
    assert.match(productPageSource, /image:\s*getProductCartImage\(product\)/);
    assert.match(productPageSource, /image=\{getProductCartImage\(product\)\}/);
    assert.doesNotMatch(productPageSource, /isMobileCtaVisible/);
    assert.doesNotMatch(productPageSource, /window\.scrollY > 120/);
    assert.match(cartActionBarSource, /cart-action-bar-shell/);
    assert.match(cartActionBarSource, /translate3d\(-50%, \$\{isCartActionVisible \? '0px' : '22px'\}, 0\)/);
    assert.match(cartActionBarSource, /в корзине:/);
    assert.match(cartActionBarSource, /ИЗМЕНИТЬ/);
    assert.match(cartActionBarSource, /КУПИТЬ/);
    assert.doesNotMatch(productPageSource, /<CartOverlay|isCartOpen|setIsCartOpen/);

    assert.match(productPageSource, /videoPoster=\{nextProduct\.mobile_video_poster\}/);
});

test("mobile product page renders the cart CTA as a collapsible cart bar", () => {
    assert.match(productPageSource, /CartActionBar/);
    assert.doesNotMatch(productPageSource, /mag-cta-content/);
    assert.match(productPageSource, /handleMobileBuyClick/);
    assert.match(productPageSource, /router\.push\('\/checkout'\)/);
    assert.match(productPageSource, /const handleProductBack = useCallback\(\(\) => \{/);
    assert.match(productPageSource, /window\.history\.length > 1/);
    assert.match(productPageSource, /router\.back\(\)/);
    assert.match(productPageSource, /router\.push\('\/'\)/);
    assert.match(productPageSource, /onClick=\{handleProductBack\}/);
    assert.match(productPageSource, /top:\s*`calc\(clamp\(70px, 18\.92vw, 121px\) \+ \$\{PRODUCT_MOBILE_HEADER_TOP_OFFSET\} - 18px\)`/);
    assert.match(productPageSource, /z-\[120\]/);
    assert.match(productPageSource, /h-\[40px\]\s+w-\[40px\]/);
    assert.match(productPageSource, /currentProductCartItem/);
    assert.match(productPageSource, /cartItemId=\{currentProductCartItem\?\.id\}/);
    assert.match(landingSource, /cartItemId=\{catalog\.landingCartItem\?\.id\}/);
    assert.match(landingSource, /activeItemId/);
    assert.match(productPageSource, /visible=\{hasScrolled\}/);
    assert.match(landingSource, /visible=\{catalog\.hasCartItems\}/);
    assert.doesNotMatch(productPageSource, /window\.scrollY > 120/);
    assert.doesNotMatch(landingSource, /window\.scrollY > 120/);

    assert.match(cartActionBarSource, /CART_ACTION_CONTENT_GLOW_COLLAPSED_HEIGHT = '300px'/);
    assert.match(cartActionBarSource, /CART_ACTION_CONTENT_GLOW_EXPANDED_HEIGHT = '100px'/);
    assert.match(cartActionBarSource, /CART_ACTION_EXPANDED_BASE_HEIGHT = 510/);
    assert.match(cartActionBarSource, /CART_ACTION_EXPANDED_MAX_HEIGHT = 560/);
    assert.match(cartActionBarSource, /CART_ACTION_MAX_VIEWPORT_WIDTH = 640/);
    assert.doesNotMatch(cartActionBarSource, /CART_ACTION_COLLAPSED_HEIGHT/);
    assert.match(cartActionBarSource, /const \[isExpanded, setIsExpanded\] = React\.useState\(false\)/);
    assert.match(cartActionBarSource, /setExpandedFromHandle\(true\)/);
    assert.match(cartActionBarSource, /width:\s*'min\(calc\(100vw - 14px\), 660px\)'/);
    assert.match(cartActionBarSource, /className="cart-action-bar-shell[\s\S]*?background:\s*'transparent'/s);
    assert.doesNotMatch(cartActionBarSource, /background:\s*isPanelExpandedPresentation \? CART_ACTION_SURFACE_BACKGROUND : 'transparent'/);
    assert.match(cartActionBarSource, /border:\s*0/);
    assert.match(cartActionBarSource, /boxShadow:\s*'none'/);
    assert.match(cartActionBarSource, /bottom:\s*`calc\(var\(--cart-action-bar-bottom, 5px\) \+ \$\{cartActionShellBottomLift\.toFixed\(2\)\}px\)`/);
    assert.doesNotMatch(cartActionBarSource, /bottom:\s*'calc\(40px \+ env\(safe-area-inset-bottom\)\)'/);
    assert.match(globalStylesSource, /--cart-action-bar-bottom:\s*5px/);
    assert.doesNotMatch(globalStylesSource, /--cart-action-bar-bottom:\s*40px/);
    assert.match(globalStylesSource, /html\[data-browser-surface="pwa"\],[\s\S]*html\[data-browser-surface="safari26"\],[\s\S]*--cart-action-bar-bottom:\s*20px/s);
    assert.doesNotMatch(globalStylesSource, /data-cart-action-expanded|app-visual-viewport-bottom-offset|app-viewport-bottom-extension/);
    assert.match(globalStylesSource, /--constructor-panel-bottom:\s*5px/);
    assert.doesNotMatch(globalStylesSource, /constructorVisibleViewport::after/);
    assert.doesNotMatch(cartActionBarSource, /cart-action-bar-expanded-surface|cart-action-bar-compact-panel-surface/);
    assert.match(cartActionBarSource, /const CART_ACTION_SURFACE_BACKGROUND = 'rgb\(255 255 255 \/ 70%\)'/);
    assert.match(cartActionBarSource, /const CART_ACTION_PRODUCT_SECTION_BACKGROUND = 'rgb\(255 255 255 \/ 30%\)'/);
    assert.match(cartActionBarSource, /className="cart-action-bar-content[\s\S]*?backgroundColor:\s*isLiquidV2[\s\S]*?\? isPanelExpandedPresentation \? 'rgb\(255 255 255 \/ 80%\)' : 'transparent'[\s\S]*?: isCompactCollapsedPresentation \? 'rgb\(255 255 255 \/ 0%\)' : cartActionSurfaceBackground/s);
    assert.match(cartActionBarSource, /className="cart-action-bar-content[\s\S]*?border:\s*`1px solid \$\{isCompactCollapsedPresentation \? 'transparent' : cartActionSurfaceBorderColor\}`/s);
    assert.match(cartActionBarSource, /className="cart-action-bar-content[\s\S]*?boxShadow:\s*isLiquidV2 \|\| isCompactCollapsedPresentation[\s\S]*?'rgba\(0, 0, 0, 0\.1\) 0px 8px 32px/s);
    assert.match(cartActionBarSource, /overflow:\s*'visible'/);
    assert.match(cartActionBarSource, /usePreferredCartItemOnly\?: boolean/);
    assert.match(cartActionBarSource, /usePreferredCartItemOnly = false/);
    assert.match(cartActionBarSource, /if \(usePreferredCartItemOnly\) return preferredItem/);
    assert.match(cartActionBarSource, /const \[isRendered, setIsRendered\] = React\.useState\(visible\)/);
    assert.match(cartActionBarSource, /setIsRendered\(true\)/);
    assert.match(cartActionBarSource, /window\.setTimeout\(\(\) => setIsRendered\(false\),\s*CART_ACTION_EXIT_MS\)/);
    assert.match(cartActionBarSource, /if \(!isRendered\) return null/);
    assert.doesNotMatch(cartActionBarSource, /if \(!visible \|\| totalQuantity === 0 \|\| !currentCartItem\) return null/);
    assert.doesNotMatch(cartActionBarSource, /height:\s*isExpanded \? CART_ACTION_EXPANDED_HEIGHT : CART_ACTION_COLLAPSED_HEIGHT/);
    assert.match(cartActionBarSource, /transition:\s*isPanelDragActive[\s\S]*?: isCartActionVisible/s);
    assert.match(cartActionBarSource, /cart-action-bar-content-glow/);
    assert.match(cartActionBarSource, /width:\s*'100vw'/);
    assert.match(cartActionBarSource, /height:\s*CART_ACTION_CONTENT_GLOW_COLLAPSED_HEIGHT/);
    assert.match(cartActionBarSource, /background:\s*CART_ACTION_CONTENT_GLOW_COLLAPSED_GRADIENT/);
    assert.match(cartActionBarSource, /transform:\s*'translateX\(-50%\) translateY\(-50%\)'/);
    assert.match(cartActionBarSource, /cart-action-bar-content-glow pointer-events-none absolute bottom-\[-30px\] left-0 z-0/);
    assert.match(cartActionBarSource, /width:\s*'100%'/);
    assert.match(cartActionBarSource, /height:\s*CART_ACTION_CONTENT_GLOW_EXPANDED_HEIGHT/);
    assert.match(cartActionBarSource, /background:\s*CART_ACTION_CONTENT_GLOW_EXPANDED_GRADIENT/);
    assert.match(cartActionBarSource, /CART_ACTION_CONTENT_GLOW_COLLAPSED_GRADIENT = 'radial-gradient\(171\.77% 41\.81% at 50% 50%/);
    assert.match(cartActionBarSource, /CART_ACTION_CONTENT_GLOW_EXPANDED_GRADIENT = 'radial-gradient\(171\.77% 41\.81% at 50% 50%/);
    assert.match(cartActionBarSource, /cart-action-bar-content relative z-10 flex flex-col/);
    assert.doesNotMatch(cartActionBarSource, /cart-action-bar-content relative z-10 flex h-full/);
    assert.match(cartActionBarSource, /text-\[10px\][\s\S]{0,80}text-\[#9F9F9F\]/);
    assert.match(cartActionBarSource, /cart-action-bar-handle/);
    assert.match(cartActionBarSource, /cart-action-bar-handle h-\[2px\] w-\[50px\]/);
    assert.doesNotMatch(cartActionBarSource, /cart-action-bar-handle absolute/);
    assert.match(cartActionBarSource, /onPointerDown=\{handleHandlePointerDown\}/);
    assert.match(cartActionBarSource, /onPointerMove=\{handleHandlePointerMove\}/);
    assert.match(cartActionBarSource, /onPointerUp=\{handleHandlePointerUp\}/);
    assert.match(cartActionBarSource, /onPointerCancel=\{handleHandlePointerCancel\}/);
    assert.match(cartActionBarSource, /style=\{\{ touchAction: 'none' \}\}/);
    assert.match(cartActionBarSource, /setPointerCapture\(event\.pointerId\)/);
    assert.match(cartActionBarSource, /DRAG_START_THRESHOLD = 8/);
    assert.match(cartActionBarSource, /DRAG_SNAP_MIN_DISTANCE = 96/);
    assert.match(cartActionBarSource, /DRAG_SNAP_PROGRESS = 0\.2/);
    assert.match(cartActionBarSource, /handleZone\.setPointerCapture\(event\.pointerId\)/);
    assert.match(cartActionBarSource, /deltaY <= -snapDistance/);
    assert.match(cartActionBarSource, /deltaY >= snapDistance/);
    assert.match(cartActionBarSource, /setIsExpanded\(true\)/);
    assert.match(cartActionBarSource, /setIsExpanded\(false\)/);
    assert.match(cartActionBarSource, /pr-\[25px\]/);
    assert.doesNotMatch(cartActionBarSource, /right-\[25px\]/);
    assert.match(cartActionBarSource, /!isPanelExpandedPresentation && totalQuantity > 0/);
    assert.match(cartActionBarSource, /cart-action-bar-product-panel/);
    assert.match(cartActionBarSource, /cart-action-bar-product-panel relative z-10 mt-\[clamp\(4px,1\.081vw,7px\)\] flex min-h-0/);
    assert.doesNotMatch(cartActionBarSource, /cart-action-bar-product-panel absolute/);
    assert.doesNotMatch(cartActionBarSource, /cart-action-bar-product-panel absolute left-0 right-0/);
    assert.doesNotMatch(cartActionBarSource, /CART_ACTION_PANEL_GRADIENT/);
    assert.doesNotMatch(cartActionBarSource, /cart-action-bar-product-gradient/);
    assert.match(
        cartActionBarSource,
        /background:\s*'transparent'/,
    );
    assert.match(cartActionBarSource, /radial-gradient\(171\.77% 41\.81% at 50% 50%/);
    assert.doesNotMatch(cartActionBarSource, /rgba\(255, 255, 255, 0\.00\) 97\.12%\), #F3F3F3/);
    assert.match(
        cartActionBarSource,
        /border:\s*'1px solid'[\s\S]*?borderColor:\s*isCompactCollapsedPresentation[\s\S]*?'rgba\(255, 255, 255, 0\.3\)'[\s\S]*?: '#D9D9D9'/,
    );
    assert.doesNotMatch(cartActionBarSource, /height:\s*isExpanded \? '497px' : '54px'/);
    assert.doesNotMatch(cartActionBarSource, /flex:\s*isExpanded \? '1 1 auto' : '0 0 auto'/);
    assert.match(cartActionBarSource, /const productPanelRef = React\.useRef<HTMLDivElement \| null>\(null\)/);
    assert.match(cartActionBarSource, /const \[collapsedPanelHeight, setCollapsedPanelHeight\] = React\.useState\(\s*collapsedHeight \?\? COLLAPSED_PRODUCT_MIN_HEIGHT,\s*\)/);
    assert.match(cartActionBarSource, /isExpanded\s*\?\s*`\$\{expandedPanelHeight\}px`\s*:\s*`\$\{collapsedPanelHeight\}px`/);
    assert.match(cartActionBarSource, /`height \$\{CART_ACTION_EXPAND_MS\}ms cubic-bezier\(0\.22, 1, 0\.36, 1\)`/);
    assert.match(cartActionBarSource, /cart-action-bar-collapsed-layer[\s\S]*?padding:\s*'clamp\(10px, 2\.703vw, 17px\) clamp\(20px, 5\.405vw, 35px\)'/s);
    assert.match(cartActionBarSource, /gap-\[clamp\(30px,8\.108vw,52px\)\]/);
    assert.match(cartActionBarSource, /font-manrope text-\[12px\] font-normal leading-normal text-\[#2D2D2D\]/);
    assert.match(cartActionBarSource, /cart-action-bar-product-summary/);
    assert.match(cartActionBarSource, /cart-action-bar-product-summary[^"]*flex[^"]*flex-col/);
    assert.doesNotMatch(cartActionBarSource, /cart-action-bar-product-summary[^"]*gap-\[8px\]/);
    assert.match(cartActionBarSource, /cart-action-bar-product-meta/);
    assert.match(cartActionBarSource, /text-\[10px\]/);
    assert.match(cartActionBarSource, /cart-action-bar-add/);
    assert.match(cartActionBarSource, /background:\s*'rgba\(255, 255, 255, 0\.6\)'/);
    assert.match(cartActionBarSource, /border:\s*'1px solid #E5E5E5'/);
    assert.match(cartActionBarSource, /cart-action-bar-stepper/);
    assert.match(cartActionBarSource, /w-\[clamp\(135px,36\.486vw,234px\)\]/);
    assert.match(cartActionBarSource, /h-\[clamp\(27px,7\.297vw,47px\)\]/);
    assert.match(cartActionBarSource, /grid-cols-\[clamp\(37px,10vw,64px\)_minmax\(0,1fr\)_clamp\(37px,10vw,64px\)\]/);
    assert.match(cartActionBarSource, /text-\[16px\] font-medium leading-normal text-\[#545454\]/);
    assert.match(cartActionBarSource, /justify-end/);
    assert.match(cartActionBarSource, /justify-center/);
    assert.match(cartActionBarSource, /justify-start/);
    assert.match(cartActionBarSource, /currentCartItem/);
    assert.match(cartActionBarSource, /<CartQuantityControl item=\{currentCartItem\} updateQuantity=\{updateQuantity\} variant="collapsed"/);
    assert.match(cartActionBarSource, /updateQuantity\(item\.id,\s*item\.quantity - 1\)/);
    assert.match(cartActionBarSource, /updateQuantity\(item\.id,\s*item\.quantity \+ 1\)/);
    assert.match(cartActionBarSource, /cart-action-bar-footer relative z-10 mb-\[7px\]/);
    assert.doesNotMatch(cartActionBarSource, /cart-action-bar-footer absolute/);
    assert.match(cartActionBarSource, /style=\{\{ marginTop: '9px' \}\}/);
    assert.doesNotMatch(cartActionBarSource, /marginTop: isExpanded \? '13px' : '2px'/);
    assert.match(cartActionBarSource, /text-\[14px\] font-semibold leading-\[11\.582px\] text-\[#676767\]/);
    assert.match(cartActionBarSource, /cart-action-bar-edit-icon/);
    assert.match(cartActionBarSource, /src="\/edit_icon\.svg"/);
    assert.doesNotMatch(cartActionBarSource, /M9\.5 3\.5h5/);
    assert.match(cartActionBarSource, /width:\s*'2px'/);
    assert.match(cartActionBarSource, /height:\s*'14px'/);

    assert.match(cartActionBarSource, /cart-action-bar-expanded-cart-items/);
    assert.match(cartActionBarSource, /items\.map\(item => \([\s\S]*?<CartItemRow/);
    assert.match(cartActionBarSource, /cart-action-bar-add-product-card/);
    assert.match(cartActionBarSource, /cart-action-bar-coupon-section/);
    assert.match(cartActionBarSource, /cart-action-bar-coupon-dropdown/);
    assert.match(cartActionBarSource, /cart-action-bar-totals-section/);
    assert.match(cartActionBarSource, /cart-action-bar-grand-total-section/);
    assert.match(cartActionBarSource, /cart-action-bar-details-popup/);
});

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

test("mobile product page keeps gallery and review media visually tight", () => {
    assert.match(productPageSource, /w-screen relative left-1\/2 -translate-x-1\/2 aspect-square/);
    assert.doesNotMatch(productPageSource, /w-screen relative left-1\/2 -translate-x-1\/2 aspect-4\/5/);
    assert.match(productPageSource, /alt=\{`Gallery \$\{index\}`\}[\s\S]*className="object-cover object-top"/);
    assert.doesNotMatch(productPageSource, /alt=\{`Gallery \$\{index\}`\}[\s\S]{0,240}className="object-scale-down object-top"/);
    assert.doesNotMatch(productPageSource, /className="object-contain"\s+onLoad=\{\(\) => setLoadedImagesCount/);
    assert.match(productPageSource, /overflow-x-auto scrollbar-hide/);
    assert.match(productPageSource, /background:\s*'#FFF'/);
    assert.match(productPageSource, /h-\[clamp\(120px,31vw,198px\)\]/);
    assert.match(productPageSource, /h-full aspect-square shrink-0/);
});

test("catalog shows a mobile floating cart button as soon as the cart has items", () => {
    assert.match(landingSource, /useCartStore/);
    assert.match(landingSource, /CartActionBar/);
    assert.doesNotMatch(landingSource, /isFloatingCartVisible/);
    assert.doesNotMatch(landingSource, /window\.scrollY > 120/);
    assert.match(landingSource, /activeItemId/);
    assert.match(landingSource, /landingCartItem/);
    assert.match(landingSource, /goToCheckout/);
    assert.match(landingSource, /visible=\{catalog\.hasCartItems\}/);
    assert.match(landingSource, /router\.push\('\/checkout'\)/);
    assert.doesNotMatch(landingSource, />\s*Корзина\s*<\/button>/);
    assert.doesNotMatch(landingSource, /CartOverlay|isCartOpen|setIsCartOpen/);
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

test("mobile related products scale on larger phones", () => {
    assert.match(productPageSource, /h-\[clamp\(450px,121\.622vw,779px\)\]/);
    assert.match(productPageSource, /px-\[clamp\(16px,4\.32vw,28px\)\]/);
    assert.match(productPageSource, /gap-y-\[clamp\(20px,5\.4vw,35px\)\]/);
    assert.match(productPageSource, /w-\[clamp\(100px,27\.027vw,173px\)\]/);
    assert.match(productPageSource, /h-\[clamp\(127px,34\.324vw,220px\)\]/);
    assert.match(productPageSource, /size="clamp\(8px,2\.16vw,14px\)"/);
    assert.match(productPageSource, /size="clamp\(10px,2\.7vw,17px\)"/);
});
