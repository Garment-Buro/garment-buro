import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const cartActionBarSource = [
    path.join(root, "components", "cart", "CartActionBar.tsx"),
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
    path.join(root, "hooks", "media", "useInlineAutoplayVideo.ts"),
    path.join(root, "lib", "api", "orders.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const globalsSource = fs.readFileSync(path.join(root, "app", "globals.css"), "utf8");
const productPageSource = [
    path.join(root, "components", "product", "ProductPageClient.tsx"),
    path.join(root, "components", "product", "ProductMobileLayout.tsx"),
    path.join(root, "hooks", "product", "useProductPage.ts"),
    path.join(root, "lib", "products", "constants.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const landingPageSource = fs.readFileSync(path.join(root, "components", "shared", "LandingPage.tsx"), "utf8");

test("cart action bar has a staged mount lifecycle so slide-up can play on enter", () => {
    assert.match(cartActionBarSource, /const CART_ACTION_ENTER_MS = 420/);
    assert.match(cartActionBarSource, /const CART_ACTION_EXIT_MS = 340/);
    assert.match(cartActionBarSource, /const \[isVisibleFrame,\s*setIsVisibleFrame\] = React\.useState\(false\)/);
    assert.match(cartActionBarSource, /window\.requestAnimationFrame\(\(\) => \{\s*frameId = window\.requestAnimationFrame\(\(\) => setIsVisibleFrame\(true\)\);\s*\}\)/);
    assert.match(cartActionBarSource, /window\.cancelAnimationFrame\(frameId\)/);
});

test("cart action bar does not replay fade-up while it is already visible", () => {
    assert.doesNotMatch(cartActionBarSource, /cartMotionKey/);
    assert.doesNotMatch(cartActionBarSource, /previousCartMotionKeyRef/);
    assert.doesNotMatch(cartActionBarSource, /cartReplayMotionIndex/);
    assert.doesNotMatch(cartActionBarSource, /cartReplayAnimation/);
    assert.doesNotMatch(cartActionBarSource, /animation:\s*cartReplayAnimation/);
    assert.doesNotMatch(globalsSource, /@keyframes cartActionBarFadeUpReplayEven/);
    assert.doesNotMatch(globalsSource, /@keyframes cartActionBarFadeUpReplayOdd/);
});

test("V2 can remain expanded while the cart is empty without changing the catalog default", () => {
    assert.match(cartActionBarSource, /allowEmptyExpand\s*=\s*false/);
    assert.match(cartActionBarSource, /isCartOpen && \(items\.length > 0 \|\| allowEmptyExpand\)/);
    assert.match(cartActionBarSource, /\[allowEmptyExpand,\s*isCartOpen,\s*items\.length\]/);
});

test("cart action bar enters at final opacity and exits with a short smooth fade out", () => {
    assert.match(cartActionBarSource, /const shouldShowCartAction = visible \|\| isExpanded/);
    assert.match(cartActionBarSource, /if \(shouldShowCartAction\) \{/);
    assert.match(cartActionBarSource, /}, \[shouldShowCartAction\]\)/);
    assert.match(cartActionBarSource, /if \(!visible && !isExpanded\) \{/);
    assert.match(cartActionBarSource, /const isCartActionVisible = shouldShowCartAction && isVisibleFrame/);
    assert.doesNotMatch(cartActionBarSource, /const isCartActionExiting = isRendered && !visible/);
    assert.match(cartActionBarSource, /transform:\s*`translate3d\(-50%, \$\{isCartActionVisible \? '0px' : '22px'\}, 0\)`/);
    assert.match(cartActionBarSource, /opacity:\s*shouldShowCartAction \? 1 : 0/);
    assert.match(cartActionBarSource, /isCartActionVisible[\s\S]*?`transform \$\{CART_ACTION_ENTER_MS\}ms cubic-bezier\(0\.22, 1, 0\.36, 1\), bottom \$\{CART_ACTION_EXPAND_MS\}ms/s);
    assert.doesNotMatch(cartActionBarSource, /\?\s*`opacity \$\{CART_ACTION_ENTER_MS\}ms ease/);
    assert.match(cartActionBarSource, /transform \$\{CART_ACTION_EXIT_MS\}ms cubic-bezier\(0\.4, 0, 0\.2, 1\)/);
    assert.doesNotMatch(cartActionBarSource, /visible \? '0px' : '110%'/);
});

test("expanded cart grows only through the product panel height", () => {
    assert.match(cartActionBarSource, /const CART_ACTION_BASE_VIEWPORT_WIDTH = 370/);
    assert.match(cartActionBarSource, /const CART_ACTION_MAX_VIEWPORT_WIDTH = 640/);
    assert.match(cartActionBarSource, /const CART_ACTION_EXPANDED_BASE_HEIGHT = 510/);
    assert.match(cartActionBarSource, /const CART_ACTION_EXPANDED_MIN_HEIGHT = 280/);
    assert.match(cartActionBarSource, /const CART_ACTION_EXPANDED_MAX_HEIGHT = 560/);
    assert.match(cartActionBarSource, /const viewportHeight = window\.visualViewport\?\.height \?\? window\.innerHeight/);
    assert.match(cartActionBarSource, /document\.querySelector\('header'\)\?\.getBoundingClientRect\(\)/);
    assert.match(cartActionBarSource, /Math\.max\(0, headerRect\.height, headerRect\.bottom\)/);
    assert.match(cartActionBarSource, /viewportHeight[\s\S]*?- CART_ACTION_EXPANDED_VIEWPORT_GAP[\s\S]*?- CART_ACTION_GUEST_AUTH_VIEWPORT_RESERVE[\s\S]*?- headerClearance/);
    assert.match(cartActionBarSource, /window\.visualViewport\?\.addEventListener\('resize', syncCartPanelGeometry\)/);
    assert.match(cartActionBarSource, /setExpandedPanelHeight\(Math\.round\(Math\.min\(\s*widthScaledHeight,\s*viewportLimitedHeight,\s*CART_ACTION_EXPANDED_MAX_HEIGHT,\s*\)\)\)/s);
    assert.doesNotMatch(cartActionBarSource, /CART_ACTION_EXPANDED_BAR_HEIGHT/);
    assert.doesNotMatch(cartActionBarSource, /height:\s*isExpanded\s*\?\s*CART_ACTION_EXPANDED_BAR_HEIGHT\s*:\s*undefined/);
    assert.match(cartActionBarSource, /isExpanded\s*\?\s*`\$\{expandedPanelHeight\}px`\s*:\s*`\$\{collapsedPanelHeight\}px`/);
    assert.match(cartActionBarSource, /className="cart-action-bar-collapsed-layer[\s\S]*?padding:\s*'clamp\(10px, 2\.703vw, 17px\) clamp\(20px, 5\.405vw, 35px\)'/s);
    assert.match(cartActionBarSource, /const CART_ACTION_EXPAND_MS = 560/);
    assert.match(cartActionBarSource, /const CART_ACTION_SURFACE_BACKGROUND = 'rgb\(255 255 255 \/ 70%\)'/);
    assert.match(cartActionBarSource, /const CART_ACTION_PRODUCT_SECTION_BACKGROUND = 'rgb\(255 255 255 \/ 30%\)'/);
    assert.match(cartActionBarSource, /const collapsedLayerBackground = `rgb\(255 255 255 \/ \$\{\(collapsedContentProgress \* 40\)\.toFixed\(2\)\}%\)`/);
    assert.match(cartActionBarSource, /const CART_ACTION_SECTION_GAP_BACKGROUND = 'rgba\(243, 243, 243, 0\.7\)'/);
    assert.match(cartActionBarSource, /className="cart-action-bar-section-separator w-full shrink-0"[\s\S]*?background:\s*CART_ACTION_SECTION_GAP_BACKGROUND/);
    assert.match(cartActionBarSource, /className="cart-action-bar-content[\s\S]*?backgroundColor:\s*isLiquidV2[\s\S]*?\? isPanelExpandedPresentation \? 'rgb\(255 255 255 \/ 80%\)' : 'transparent'[\s\S]*?: isCompactCollapsedPresentation \? 'rgb\(255 255 255 \/ 0%\)' : cartActionSurfaceBackground/s);
    assert.match(cartActionBarSource, /overflowY:\s*'hidden'/);
    assert.match(cartActionBarSource, /height:\s*'100%'/);
    assert.match(cartActionBarSource, /maxHeight:\s*'100%'/);
    assert.doesNotMatch(cartActionBarSource, /MAX_EXPANDED_HEIGHT/);
    assert.doesNotMatch(cartActionBarSource, /calc\(100dvh - 200px\)/);
});

test("collapsed cart height is measured from inner content, not from the panel height", () => {
    assert.doesNotMatch(cartActionBarSource, /productPanelRef\.current\?\.scrollHeight/);
    assert.match(cartActionBarSource, /productPanel\.querySelector<HTMLElement>\('\.cart-action-bar-collapsed-layer'\)/);
    assert.match(cartActionBarSource, /const collapsedContent = collapsedLayer\?\.firstElementChild/);
    assert.match(cartActionBarSource, /getBoundingClientRect\(\)\.height/);
    assert.match(cartActionBarSource, /Number\.parseFloat\(panelStyles\.paddingTop\)/);
    assert.match(cartActionBarSource, /Number\.parseFloat\(panelStyles\.borderTopWidth\)/);
    assert.match(cartActionBarSource, /Number\.parseFloat\(collapsedLayerStyles\.paddingTop\)/);
    assert.match(cartActionBarSource, /setCollapsedPanelHeight\(Math\.round\(COLLAPSED_PRODUCT_MIN_HEIGHT \* widthRatio\)\)/);
});

test("new compact glass cart keeps the legacy collapsed version and restores expanded visuals", () => {
    assert.match(cartActionBarSource, /export type CartCollapsedVariant = 'legacy' \| 'glass-compact' \| 'liquid-v2'/);
    assert.match(cartActionBarSource, /collapsedVariant = 'glass-compact'/);
    assert.match(cartActionBarSource, /isCompactCollapsedPresentation:\s*\([\s\S]*?collapsedVariant === 'glass-compact' && expansionProgress <= 0\.001[\s\S]*?\) \|\| \([\s\S]*?collapsedVariant === 'liquid-v2' && expansionProgress <= 0\.001/);
    assert.match(cartActionBarSource, /\{!isCompactCollapsedPresentation && !isPanelExpandedPresentation \? \([\s\S]*?cart-action-bar-content-glow[\s\S]*?\) : null\}/);
    assert.match(cartActionBarSource, /\{isPanelExpandedPresentation \? \([\s\S]*?cart-action-bar-content-glow pointer-events-none absolute bottom-\[-30px\] left-0 z-0[\s\S]*?width:\s*'100%'[\s\S]*?height:\s*CART_ACTION_CONTENT_GLOW_EXPANDED_HEIGHT/);
    assert.match(cartActionBarSource, /collapsedVariant === 'legacy' && !isPanelExpandedPresentation && totalQuantity > 0/);
    assert.match(cartActionBarSource, /cart-action-bar-footer-reveal[\s\S]*?maxHeight:\s*`\$\{30 \* footerRevealProgress\}px`/s);
    assert.match(cartActionBarSource, /background:\s*'transparent'/);
    assert.match(cartActionBarSource, /border:\s*0/);
    assert.match(cartActionBarSource, /boxShadow:\s*'none'/);
    assert.match(cartActionBarSource, /className="cart-action-bar-content relative z-10 flex flex-col rounded-\[20px\][\s\S]*?backgroundColor:\s*isLiquidV2[\s\S]*?\? isPanelExpandedPresentation \? 'rgb\(255 255 255 \/ 80%\)' : 'transparent'[\s\S]*?: isCompactCollapsedPresentation \? 'rgb\(255 255 255 \/ 0%\)' : cartActionSurfaceBackground[\s\S]*?border:\s*`1px solid \$\{isCompactCollapsedPresentation \? 'transparent' : cartActionSurfaceBorderColor\}`/s);
    assert.match(cartActionBarSource, /backdropFilter:\s*cartActionSurfaceBackdropFilter/);
    assert.doesNotMatch(cartActionBarSource, /cart-action-bar-expanded-surface|cart-action-bar-compact-panel-surface|expandedSurfaceProgress|compactPanelSurfaceProgress/);
});

test("cart drag cannot stretch above the expanded panel height", () => {
    assert.match(cartActionBarSource, /const maxExpandOffset = Math\.max\(0, expandedPanelHeight - collapsedPanelHeight\)/);
    assert.match(cartActionBarSource, /const clampedOffset = Math\.max\(-maxExpandOffset, Math\.min\(0, deltaY\)\)/);
    assert.match(cartActionBarSource, /Math\.min\(expandedPanelHeight, collapsedPanelHeight \+ Math\.abs\(dragOffset\)\)/);
});

test("expanded cart renders the requested Figma cart sections", () => {
    assert.match(cartActionBarSource, /Доставка в пункт выдачи/);
    assert.match(cartActionBarSource, /Доставка курьером/);
    assert.match(cartActionBarSource, /Получатель/);
    assert.match(cartActionBarSource, /cart-action-bar-expanded-cart-items/);
    assert.match(cartActionBarSource, /Корзина/);
    assert.match(cartActionBarSource, /items\.map\(item => \([\s\S]*?<CartItemRow/);
    assert.match(cartActionBarSource, /<span>Подробнее<\/span>/);
    assert.match(cartActionBarSource, /cart-action-bar-coupon-section/);
    assert.match(cartActionBarSource, /Купон/);
    assert.match(cartActionBarSource, /Выберите купон/);
    assert.match(cartActionBarSource, /cart-action-bar-coupon-dropdown/);
    assert.match(cartActionBarSource, /Первый заказ/);
    assert.match(cartActionBarSource, /Уровень L/);
    assert.match(cartActionBarSource, /10 изделий/);
    assert.match(cartActionBarSource, /cart-action-bar-totals-section/);
    assert.match(cartActionBarSource, /Товары/);
    assert.match(cartActionBarSource, /Скидка/);
    assert.match(cartActionBarSource, /Итого/);
    assert.match(cartActionBarSource, /Способ оплаты/);
    assert.match(cartActionBarSource, /const PaymentCardIcon = \(\) => \(/);
    assert.match(cartActionBarSource, /Оплата по QR-коду/);
    assert.match(cartActionBarSource, /СБП/);
    assert.match(cartActionBarSource, /Банковская карта/);
    assert.match(cartActionBarSource, /МИР, Visa/);
    assert.match(cartActionBarSource, /Я соглашаюсь с/);
    assert.match(cartActionBarSource, /политику конфиденциальности/);
});

test("expanded cart content uses transparent framing with thirty-percent inner sections", () => {
    assert.match(cartActionBarSource, /className="flex h-full w-full flex-col overflow-y-auto"/);
    assert.match(cartActionBarSource, /className="cart-action-bar-content[\s\S]*?backgroundColor:\s*isLiquidV2[\s\S]*?\? isPanelExpandedPresentation \? 'rgb\(255 255 255 \/ 80%\)' : 'transparent'[\s\S]*?: isCompactCollapsedPresentation \? 'rgb\(255 255 255 \/ 0%\)' : cartActionSurfaceBackground/s);
    assert.match(cartActionBarSource, /const CART_ACTION_PRODUCT_SECTION_BACKGROUND = 'rgb\(255 255 255 \/ 30%\)'/);
    assert.equal((cartActionBarSource.match(/background:\s*CART_ACTION_PRODUCT_SECTION_BACKGROUND/g) ?? []).length, 7);
    assert.match(cartActionBarSource, /cart-action-bar-collapsed-layer[\s\S]*?height:\s*`\$\{collapsedPanelHeight\}px`[\s\S]*?backgroundColor:\s*collapsedLayerBackground/s);
    assert.doesNotMatch(cartActionBarSource, /className="flex h-full w-full flex-col overflow-y-auto"[\s\S]{0,500}?background:/);
    assert.match(cartActionBarSource, /const ExpandedCartSeparator = \(\) => \(/);
    assert.match(cartActionBarSource, /height:\s*'clamp\(8px, 2\.162vw, 14px\)'/);
    assert.match(cartActionBarSource, /width:\s*'100%'/);
    assert.match(cartActionBarSource, /maxWidth:\s*'72%'/);
});

test("expanded cart delivery and recipient spacing matches compact layout", () => {
    assert.doesNotMatch(cartActionBarSource, /className="flex items-center gap-\[8px\] whitespace-nowrap"/);
    assert.match(cartActionBarSource, /className="flex items-center whitespace-nowrap"/);
    assert.equal((cartActionBarSource.match(/className="flex items-center whitespace-nowrap" style=\{\{ gap: 3 \}\}/g) ?? []).length, 1);
    assert.equal((cartActionBarSource.match(/variant="delivery"/g) ?? []).length, 2);
    assert.match(cartActionBarSource, /padding:\s*'clamp\(20px, 5\.405vw, 35px\) 5px clamp\(10px, 2\.703vw, 17px\)'/);
    assert.match(cartActionBarSource, /paddingInline:\s*'max\(0px, calc\(clamp\(10px, 2\.703vw, 17px\) - 5px\)\)'/);
    assert.match(cartActionBarSource, /padding:\s*'clamp\(10px, 2\.703vw, 17px\) clamp\(10px, 2\.703vw, 17px\) clamp\(13px, 3\.514vw, 22px\)'/);
    assert.match(cartActionBarSource, /<div style=\{\{\s*paddingLeft:\s*'clamp\(25px, 6\.757vw, 43px\)'\s*\}\}>/);
    assert.ok((cartActionBarSource.match(/style=\{\{ alignItems: 'self-end' \}\}/g) ?? []).length >= 2);
    assert.match(cartActionBarSource, /cart-action-bar-payment-method[\s\S]*?paddingInline:\s*'max\(0px, calc\(clamp\(28px, 7\.568vw, 48px\) - 5px\)\)'/);
    assert.match(cartActionBarSource, /cart-action-bar-grand-total-section px-\[5px\]/);
    assert.match(cartActionBarSource, /paddingInline:\s*'max\(0px, calc\(clamp\(28px, 7\.568vw, 48px\) - 5px\)\)'/);
    assert.doesNotMatch(cartActionBarSource, /padding:\s*'14px 10px 16px'/);
    assert.doesNotMatch(cartActionBarSource, /paddingLeft:\s*25,\s*marginTop:\s*7/);
});

test("expanded cart product and add-product blocks match the 370px Figma layout", () => {
    assert.match(cartActionBarSource, /cart-action-bar-cart-item-row grid w-full grid-cols-\[clamp\(56px,15\.135vw,97px\)_minmax\(0,1fr\)_clamp\(90px,24\.324vw,156px\)\]/);
    assert.match(cartActionBarSource, /row-span-2 flex h-\[clamp\(59px,15\.946vw,102px\)\] w-\[clamp\(56px,15\.135vw,97px\)\]/);
    assert.match(cartActionBarSource, /cart-action-bar-expanded-cart-items flex w-full flex-col gap-\[clamp\(16px,4\.324vw,28px\)\]/);
    assert.match(cartActionBarSource, /<div className="flex flex-col gap-\[clamp\(16px,4\.324vw,28px\)\]">/);
    assert.match(cartActionBarSource, /col-span-2 col-start-1 ml-\[6px\]/);
    assert.match(cartActionBarSource, /\{items\.length > 0 \? \([\s\S]*?cart-action-bar-expanded-cart-items[\s\S]*?\) : null\}/);
    assert.match(cartActionBarSource, /\{showAddProductCard \? \([\s\S]*?<CartAddProductCard/);
    assert.doesNotMatch(cartActionBarSource, /\) : \(\s*<CartAddProductCard/);
    assert.match(cartActionBarSource, /cart-action-bar-add-product-card grid w-full grid-cols-\[clamp\(96px,25\.946vw,166px\)_minmax\(0,1fr\)_clamp\(124px,33\.514vw,214px\)\]/);
    assert.match(cartActionBarSource, /row-span-4 flex h-\[clamp\(169px,45\.676vw,292px\)\] w-\[clamp\(95px,25\.676vw,164px\)\]/);
    assert.match(cartActionBarSource, /cart-action-bar-add-product-title-row col-span-2 flex min-w-0 items-start justify-between gap-\[8px\]/);
    assert.match(cartActionBarSource, /col-start-3 row-start-4 flex h-\[clamp\(34px,9\.189vw,59px\)\] w-\[clamp\(124px,33\.514vw,214px\)\]/);
});

test("expanded add-product title row has a constructor edit button", () => {
    assert.match(cartActionBarSource, /cart-action-bar-add-product-title-row col-span-2 flex min-w-0 items-start justify-between gap-\[8px\]/);
    assert.match(cartActionBarSource, /className="min-w-0 pr-\[10px\] font-manrope text-\[12px\] font-medium leading-\[1\.18\] text-\[#2D2D2D\]"/);
    assert.match(cartActionBarSource, /aria-label="Изменить товар в конструкторе"[\s\S]*?onClick=\{onEdit\}/);
    assert.match(cartActionBarSource, /aria-label="Изменить товар в конструкторе"[\s\S]*?padding:\s*'6px'/);
    assert.match(cartActionBarSource, /aria-label="Изменить товар в конструкторе"[\s\S]*?borderRadius:\s*5/);
    assert.match(cartActionBarSource, /aria-label="Изменить товар в конструкторе"[\s\S]*?border:\s*'1px solid #E5E5E5'/);
    assert.match(cartActionBarSource, /aria-label="Изменить товар в конструкторе"[\s\S]*?background:\s*'rgba\(255, 255, 255, 0\.6\)'/);
    assert.match(cartActionBarSource, /aria-label="Изменить товар в конструкторе"[\s\S]*?boxShadow:\s*'0 1px 1\.8px 0 rgba\(0, 0, 0, 0\.26\)'/);
    assert.match(cartActionBarSource, /aria-label="Изменить товар в конструкторе"[\s\S]*?src="\/edit_icon\.svg"[\s\S]*?width=\{18\}[\s\S]*?height=\{18\}/);
});

test("expanded add-product card is product-page only and appears before cart items", () => {
    assert.match(cartActionBarSource, /showAddProductCard\?: boolean/);
    assert.match(cartActionBarSource, /showAddProductCard = false/);
    assert.match(productPageSource, /showAddProductCard/);
    assert.doesNotMatch(landingPageSource, /showAddProductCard/);
    assert.match(cartActionBarSource, /\{showAddProductCard \? \([\s\S]*?<CartAddProductCard[\s\S]*?\) : null\}[\s\S]*?\{items\.length > 0 \? \(/);
});

test("expanded add-product card turns its plus into a quantity stepper for the current product", () => {
    assert.match(cartActionBarSource, /cart-action-bar-add-product-stepper/);
    assert.match(cartActionBarSource, /item=\{currentCartItem\}/);
    assert.match(cartActionBarSource, /<CartQuantityControl item=\{item\} updateQuantity=\{updateQuantity\} variant="product-card"/);
    assert.match(cartActionBarSource, /onClick=\{\(\) => updateQuantity\(item\.id, item\.quantity - 1\)\}/);
    assert.match(cartActionBarSource, /\{item\.quantity\}/);
    assert.match(cartActionBarSource, /onClick=\{\(\) => updateQuantity\(item\.id, item\.quantity \+ 1\)\}/);
    assert.match(cartActionBarSource, /onClick=\{onAdd\}/);
});

test("expanded add-product plus aligns to the bottom without vertical span offset", () => {
    assert.match(cartActionBarSource, /className="col-start-3 row-start-4 flex h-\[clamp\(34px,9\.189vw,59px\)\] w-\[clamp\(124px,33\.514vw,214px\)\][^"]*self-end/);
    assert.match(cartActionBarSource, /aria-label="Добавить товар в корзину"[\s\S]*?<span>\+<\/span>/);
    assert.doesNotMatch(cartActionBarSource, /<span className="mb-\[5px\]">\+<\/span>/);
});

test("cart item edit/status control uses edit icon and only checks constructed items", () => {
    assert.match(cartActionBarSource, /item\.customization\?\.kind === 'constructor'/);
    assert.match(cartActionBarSource, /aria-label="Изменить товар"[\s\S]*?src="\/edit_icon\.svg"/);
    assert.match(cartActionBarSource, /item\.customization\?\.kind === 'constructor' \? <ConstructedItemIcon \/> : null/);
    assert.doesNotMatch(cartActionBarSource, /GearSmallIcon/);
});

test("expanded cart coupon dropdown and total blocks use Figma dimensions", () => {
    assert.match(cartActionBarSource, /cart-action-bar-coupon-section relative overflow-visible px-\[clamp\(22px,5\.946vw,38px\)\]/);
    assert.match(cartActionBarSource, /grid h-\[clamp\(25px,6\.757vw,43px\)\] min-w-0 grid-cols-\[clamp\(32px,8\.649vw,55px\)_minmax\(0,1fr\)_clamp\(22px,5\.946vw,38px\)\]/);
    assert.match(cartActionBarSource, /cart-action-bar-coupon-dropdown absolute left-\[clamp\(22px,5\.946vw,38px\)\] top-\[calc\(clamp\(64px,17\.297vw,111px\)\+5px\)\]/);
    assert.match(cartActionBarSource, /cart-action-bar-coupon-dropdown[^"\n]*bg-white/);
    assert.doesNotMatch(cartActionBarSource, /cart-action-bar-coupon-dropdown[^"\n]*bg-\[rgba\(255,255,255,0\.6\)\]/);
    assert.doesNotMatch(cartActionBarSource, /cart-action-bar-coupon-dropdown[^"\n]*bg-transparent/);
    assert.match(cartActionBarSource, /src="\/discount_header_icon\.svg"[\s\S]*?width=\{18\}[\s\S]*?height=\{13\}/);
    assert.doesNotMatch(cartActionBarSource, /text-\[9px\][^"\n]*>\s*%\s*<\/span>/);
    assert.match(cartActionBarSource, /const CART_ACTION_COUPON_BUTTON_SHADOW = '0 0\.665px 1\.196px 0 rgba\(0, 0, 0, 0\.26\)'/);
    assert.equal((cartActionBarSource.match(/boxShadow:\s*CART_ACTION_COUPON_BUTTON_SHADOW/g) ?? []).length, 2);
    assert.doesNotMatch(cartActionBarSource, /grid h-\[clamp\(25px,6\.757vw,43px\)\][^"\n]*border border-\[#8D8E8F\]/);
    assert.match(cartActionBarSource, /className="relative grid h-\[clamp\(41px,11\.081vw,71px\)\] w-full grid-cols-\[clamp\(76px,20\.541vw,131px\)_minmax\(0,1fr\)\]/);
    assert.match(cartActionBarSource, /cart-action-bar-totals-section px-\[clamp\(28px,7\.568vw,48px\)\]/);
    assert.match(cartActionBarSource, /className="flex flex-col gap-\[0px\] font-manrope text-\[10px\]/);
    assert.match(cartActionBarSource, /cart-action-bar-grand-total-section px-\[5px\]/);
    assert.match(cartActionBarSource, /mt-\[clamp\(18px,4\.865vw,31px\)\] flex flex-col gap-\[clamp\(5px,1\.351vw,9px\)\]/);
    assert.match(cartActionBarSource, /className="cart-action-bar-agreement-checkbox flex min-h-\[32px\] items-center gap-\[7px\] text-left"/);
});

test("expanded coupon dropdown keeps selection pending until apply", () => {
    assert.match(cartActionBarSource, /const \[pendingCoupon,\s*setPendingCoupon\] = useState<CartActionCoupon \| null>\(null\)/);
    assert.match(cartActionBarSource, /const \[appliedCoupon,\s*setAppliedCoupon\] = useState<CartActionCoupon \| null>\(null\)/);
    assert.match(cartActionBarSource, /pendingCoupon\?\.value === coupon\.value/);
    assert.match(cartActionBarSource, /pendingCoupon\s*\?\s*`Скидка на \$\{pendingCoupon\.label\.toLowerCase\(\)\} — \$\{pendingCoupon\.amount\}`\s*:\s*'Выберите купон'/);
    assert.match(cartActionBarSource, /onClick=\{\(\) => \{\s*setAppliedCoupon\(pendingCoupon\);\s*setIsOpen\(false\);\s*\}\}/);
    assert.match(cartActionBarSource, /backgroundImage:\s*`url\(\$\{isSelected \? '\/used_sell\.webp' : '\/unused_sell\.webp'\}\)`/);
    assert.match(cartActionBarSource, /backgroundSize:\s*'100% 100%'/);
    assert.match(cartActionBarSource, /name="arrow-up"/);
    assert.doesNotMatch(cartActionBarSource, /aria-hidden="true">⌄<\/span>/);
    assert.doesNotMatch(cartActionBarSource, /left-\[-5px\] top-1\/2 h-\[10px\] w-\[10px\]/);
    assert.doesNotMatch(cartActionBarSource, /right-\[-5px\] top-1\/2 h-\[10px\] w-\[10px\]/);
});

test("expanded cart hides discount until a coupon is applied", () => {
    assert.match(cartActionBarSource, /const discount = appliedCoupon && items\.length > 0 \? CART_ACTION_COUPON_DISCOUNT : 0/);
    assert.match(cartActionBarSource, /\{appliedCoupon \? \([\s\S]*?<div className="flex justify-between text-\[#45F472\]">[\s\S]*?<span>Скидка<\/span>[\s\S]*?<\/div>[\s\S]*?\) : null\}/);
    assert.doesNotMatch(cartActionBarSource, /React\.useState<\(typeof CART_ACTION_COUPONS\)\[number\]>\(CART_ACTION_COUPONS\[0\]\)/);
});

test("expanded cart agreements use larger stable checkbox hit targets", () => {
    assert.match(cartActionBarSource, /const renderAgreementCheckbox = \(\{[\s\S]*?id,[\s\S]*?checked,[\s\S]*?onToggle,[\s\S]*?children/);
    assert.match(cartActionBarSource, /<input[\s\S]*?type="checkbox"[\s\S]*?id=\{id\}[\s\S]*?checked=\{checked\}/);
    assert.match(cartActionBarSource, /className="relative flex h-\[28px\] w-\[28px\] shrink-0 items-center justify-center"/);
    assert.match(cartActionBarSource, /className="peer m-0 block h-\[28px\] w-\[28px\] shrink-0 appearance-none rounded-\[5px\] border border-\[#818181\][^"]*p-0/);
    assert.match(cartActionBarSource, /className="pointer-events-none absolute left-1\/2 top-1\/2 h-\[11px\] w-\[11px\] -translate-x-1\/2 -translate-y-1\/2/);
    assert.match(cartActionBarSource, /peer-checked:opacity-100/);
    assert.match(cartActionBarSource, /<label htmlFor=\{id\}/);
    assert.match(cartActionBarSource, /const agreementIdPrefix = React\.useId\(\)\.replaceAll\(':', ''\)/);
    assert.match(cartActionBarSource, /id:\s*`\$\{agreementIdPrefix\}-offer-checkbox`/);
    assert.match(cartActionBarSource, /id:\s*`\$\{agreementIdPrefix\}-policy-checkbox`/);
    assert.match(cartActionBarSource, /href="\/offer"/);
    assert.match(cartActionBarSource, /href="\/policy"/);
    assert.doesNotMatch(cartActionBarSource, /checked && <span className="h-\[7px\] w-\[7px\]/);
});

test("expanded guest cart renders a separate login card below the cart", () => {
    assert.match(cartActionBarSource, /useAuthStore\(\(state\) => state\.isAuthenticated\)/);
    assert.match(cartActionBarSource, /const \[isAuthHydrated, setIsAuthHydrated\] = React\.useState\(false\)/);
    assert.match(cartActionBarSource, /isAuthHydrated && !isAuthenticated \? \([\s\S]*?cart-action-bar-guest-auth-reveal[\s\S]*?<CartGuestAuthPrompt/s);
    assert.match(cartActionBarSource, /maxHeight:\s*`\$\{CART_ACTION_GUEST_AUTH_TOTAL_HEIGHT \* guestAuthRevealProgress\}px`/);
    assert.match(cartActionBarSource, /className="cart-action-bar-guest-auth flex w-full items-center rounded-\[14px\]"/);
    assert.match(cartActionBarSource, /minHeight: '90px'/);
    assert.match(cartActionBarSource, /height: '90px'/);
    assert.match(cartActionBarSource, /maxHeight: '90px'/);
    assert.match(cartActionBarSource, /boxSizing: 'border-box'/);
    assert.match(cartActionBarSource, /overflow: 'visible'/);
    assert.match(cartActionBarSource, /marginTop: 7/);
    assert.match(cartActionBarSource, /className="cart-action-bar-shell[\s\S]*?bottom:\s*`calc\(var\(--cart-action-bar-bottom, 5px\) \+ \$\{cartActionShellBottomLift\.toFixed\(2\)\}px\)`[\s\S]*?width:\s*'min\(calc\(100vw - 14px\), 660px\)'/s);
    assert.match(cartActionBarSource, /className="cart-action-bar-shell[\s\S]*?background:\s*'transparent'[\s\S]*?overflow:\s*'visible'/s);
    assert.doesNotMatch(cartActionBarSource, /background:\s*isPanelExpandedPresentation \? CART_ACTION_SURFACE_BACKGROUND : 'transparent'/);
    assert.doesNotMatch(cartActionBarSource, /cartActionExpanded|cart-action-bar-expanded-surface/);
    assert.match(cartActionBarSource, /className="cart-action-bar-content relative z-10 flex flex-col rounded-\[20px\][\s\S]*?backgroundColor:\s*isLiquidV2[\s\S]*?\? isPanelExpandedPresentation \? 'rgb\(255 255 255 \/ 80%\)' : 'transparent'[\s\S]*?: isCompactCollapsedPresentation \? 'rgb\(255 255 255 \/ 0%\)' : cartActionSurfaceBackground/s);
    assert.doesNotMatch(cartActionBarSource, /paddingBottom:\s*isPanelExpandedPresentation/);
    assert.match(cartActionBarSource, /const CART_ACTION_GUEST_AUTH_VIEWPORT_RESERVE = 105/);
    assert.match(cartActionBarSource, /viewportHeight[\s\S]*?- CART_ACTION_EXPANDED_VIEWPORT_GAP[\s\S]*?- CART_ACTION_GUEST_AUTH_VIEWPORT_RESERVE[\s\S]*?- headerClearance/);
    assert.match(cartActionBarSource, /window\.removeEventListener\('resize', syncCartPanelGeometry\)/);
    assert.match(cartActionBarSource, /window\.visualViewport\?\.removeEventListener\('resize', syncCartPanelGeometry\)/);
    assert.match(cartActionBarSource, /padding: '13px 11px'/);
    assert.match(cartActionBarSource, /background: 'rgb\(255 255 255\)'/);
    assert.match(cartActionBarSource, /boxShadow: '0 0 16px 3px rgba\(255, 255, 255, 0\.82\)/);
    assert.match(cartActionBarSource, /h-\[64px\] w-\[64px\]/);
    assert.match(cartActionBarSource, /src="\/logo_anim\.mp4"/);
    assert.match(cartActionBarSource, /useInlineAutoplayVideo/);
    assert.match(cartActionBarSource, /opacity:\s*hasPlayingFrame \? 1 : 0/);
    assert.doesNotMatch(cartActionBarSource, /pwa-icon-source|poster=/);
    assert.match(cartActionBarSource, />\s*Garment Buro\s*</);
    assert.match(cartActionBarSource, />\s*my collection\s*</);
    assert.match(cartActionBarSource, /text-\[18px\] font-semibold leading-normal text-\[#646464\]/);
    assert.match(cartActionBarSource, /text-\[10px\] font-normal leading-normal text-\[#AAA\]/);
    assert.match(cartActionBarSource, /className="flex min-w-0 flex-col gap-\[0px\]"/);
    assert.match(cartActionBarSource, /paddingLeft: 'clamp\(75px, 20\.27vw, 130px\)'/);
    assert.match(cartActionBarSource, /pl-0 pr-\[27px\]/);
    assert.match(cartActionBarSource, /onLogin=\{\(\) => setIsAuthPopupOpen\(true\)\}/);
    assert.match(cartActionBarSource, /<AuthPopup isOpen=\{isAuthPopupOpen\}/);
    assert.match(cartActionBarSource, /const resetCheckout[\s\S]*?setAppliedCoupon\(null\);[\s\S]*?setIsAuthPopupOpen\(false\);/);
});

test("expanded cart leaves document scrolling enabled", () => {
    assert.doesNotMatch(cartActionBarSource, /document\.documentElement\.style\.(?:overflow|overscrollBehavior)/);
    assert.doesNotMatch(cartActionBarSource, /document\.body\.style\.(?:overflow|overscrollBehavior|position|top|width|touchAction)/);
    assert.doesNotMatch(cartActionBarSource, /window\.scrollTo\(0,\s*lockedScrollY\)/);
    assert.match(cartActionBarSource, /event\.preventDefault\(\)/);
    assert.match(cartActionBarSource, /style=\{\{ touchAction: 'none' \}\}/);
    assert.match(cartActionBarSource, /touchAction:\s*'pan-y'/);
    assert.match(globalsSource, /--cart-action-bar-bottom:\s*5px/);
    assert.match(cartActionBarSource, /bottom:\s*`calc\(var\(--cart-action-bar-bottom, 5px\) \+ \$\{cartActionShellBottomLift\.toFixed\(2\)\}px\)`/);
    assert.match(globalsSource, /html\[data-browser-surface="pwa"\],[\s\S]*html\[data-browser-surface="safari26"\],[\s\S]*--cart-action-bar-bottom:\s*20px/s);
    assert.doesNotMatch(globalsSource, /data-cart-action-expanded|app-visual-viewport-bottom-offset/);
});

test("expanded cart dims the page with a clickable overlay", () => {
    assert.match(cartActionBarSource, /className="cart-action-bar-overlay fixed inset-0 z-\[101\][^"]*lg:hidden"/);
    assert.doesNotMatch(cartActionBarSource, /cart-action-bar-overlay[^\n]*bg-black\/40/);
    assert.match(cartActionBarSource, /aria-label="Свернуть корзину"/);
    assert.match(cartActionBarSource, /aria-hidden=\{!isPanelExpandedPresentation\}/);
    assert.match(cartActionBarSource, /tabIndex=\{isExpanded \? 0 : -1\}/);
    assert.match(cartActionBarSource, /const handleOverlayPointerDown = \(event: React\.PointerEvent<HTMLButtonElement>\) => \{[\s\S]*event\.preventDefault\(\);[\s\S]*event\.stopPropagation\(\);[\s\S]*setExpandedFromHandle\(false\);/);
    assert.match(cartActionBarSource, /onPointerDown=\{handleOverlayPointerDown\}/);
    assert.match(cartActionBarSource, /onClick=\{\(\) => setExpandedFromHandle\(false\)\}/);
    assert.doesNotMatch(cartActionBarSource, /isOverlayVisible|setIsOverlayVisible/);
    assert.match(cartActionBarSource, /background:\s*'#000'/);
    assert.match(cartActionBarSource, /opacity:\s*overlayRevealProgress \* 0\.5/);
    assert.match(cartActionBarSource, /pointerEvents:\s*isExpanded \? 'auto' : 'none'/);
    assert.match(cartActionBarSource, /transition:\s*isPanelDragActive[\s\S]*?`opacity \$\{CART_ACTION_REVEAL_MS\}ms cubic-bezier\(0\.22, 1, 0\.36, 1\)`/s);
    assert.match(cartActionBarSource, /willChange:\s*'opacity'/);
    assert.match(cartActionBarSource, /cart-action-bar-shell fixed left-1\/2 z-\[102\] lg:hidden/);
});

test("cart resets open, overlay, drag, and animation state when pathname changes", () => {
    assert.match(cartActionBarSource, /import \{ usePathname \} from 'next\/navigation'/);
    assert.match(cartActionBarSource, /const pathname = usePathname\(\)/);
    assert.match(cartActionBarSource, /const previousPathname = React\.useRef\(pathname\)/);
    assert.match(cartActionBarSource, /if \(previousPathname\.current === pathname\) return/);
    assert.match(cartActionBarSource, /previousPathname\.current = pathname/);
    assert.match(cartActionBarSource, /setIsCartOpen\(false\)/);
    assert.match(cartActionBarSource, /setIsExpanded\(false\)/);
    assert.match(cartActionBarSource, /setDragStartedExpanded\(false\)/);
    assert.match(cartActionBarSource, /setDragOffset\(0\)/);
    assert.match(cartActionBarSource, /setIsCouponOpen\(false\)/);
    assert.match(cartActionBarSource, /setSelectedDetailsItem\(null\)/);
    assert.match(cartActionBarSource, /setIsVisibleFrame\(false\)/);
    assert.match(cartActionBarSource, /dragStartY\.current = null/);
    assert.match(cartActionBarSource, /expandedContentRef\.current\.scrollTop = 0/);
});

test("expanded cart follows top overscroll and commits only after release or wheel settle", () => {
    assert.match(cartActionBarSource, /const TOP_OVERSCROLL_COLLAPSE_THRESHOLD = 72/);
    assert.match(cartActionBarSource, /const handleExpandedContentWheel = \(event: React\.WheelEvent<HTMLDivElement>\)/);
    assert.match(cartActionBarSource, /event\.currentTarget\.scrollTop > 0 \|\| event\.deltaY >= 0/);
    assert.match(cartActionBarSource, /expandedWheelDistance\.current \+= Math\.abs\(event\.deltaY\)/);
    assert.match(cartActionBarSource, /expandedWheelDistance\.current >= TOP_OVERSCROLL_COLLAPSE_THRESHOLD/);
    assert.match(cartActionBarSource, /const handleExpandedContentTouchStart/);
    assert.match(cartActionBarSource, /const pullPastTopDistance = touch\.clientY - startY/);
    assert.match(cartActionBarSource, /expandedTouchDragging\.current && pullPastTopDistance >= getDragSnapDistance\(\)/);
    assert.match(cartActionBarSource, /scheduleDragOffset\(Math\.min\([\s\S]*?pullPastTopDistance/);
    assert.match(cartActionBarSource, /onWheel=\{handleExpandedContentWheel\}/);
    assert.match(cartActionBarSource, /addEventListener\('touchmove', handleTouchMove, \{ passive: false \}\)/);
    assert.match(cartActionBarSource, /removeEventListener\('touchmove', handleTouchMove\)/);
    assert.match(cartActionBarSource, /handleExpandedContentTouchMove[\s\S]{0,800}?event\.preventDefault\(\)/);
});

test("cart drag previews expanded content while the panel height changes", () => {
    assert.match(cartActionBarSource, /const expansionProgress = Math\.max\(0, Math\.min\(1,/);
    assert.match(cartActionBarSource, /cart-action-bar-collapsed-layer/);
    assert.match(cartActionBarSource, /cart-action-bar-expanded-layer/);
    assert.match(cartActionBarSource, /\{renderExpandedContent\(\)\}/);
    assert.match(cartActionBarSource, /visibility:\s*isPanelExpandedPresentation \? 'visible' : 'hidden'/);
    assert.match(cartActionBarSource, /background:\s*'transparent'/);
});

test("cart expansion avoids two animated backdrop-filter surfaces in Safari PWA", () => {
    assert.doesNotMatch(cartActionBarSource, /cart-action-bar-expanded-surface|cart-action-bar-compact-panel-surface/);
    assert.doesNotMatch(cartActionBarSource, /expandedSurfaceProgress|compactPanelSurfaceProgress|productPanelGlowOpacity/);
    assert.match(cartActionBarSource, /backdropFilter:\s*isCompactCollapsedPresentation \? 'blur\(12px\) saturate\(160%\)' : 'blur\(0px\) saturate\(100%\)'/);
    assert.match(cartActionBarSource, /border-color \$\{CART_ACTION_REVEAL_MS\}ms ease/);
    assert.match(cartActionBarSource, /background-color \$\{CART_ACTION_REVEAL_MS\}ms ease/);
    assert.match(cartActionBarSource, /contain:\s*'layout paint'/);
    assert.match(cartActionBarSource, /transform:\s*'translateZ\(0\)'/);
});

test("cart drag follows the finger after a small intent threshold", () => {
    assert.match(cartActionBarSource, /const DRAG_START_THRESHOLD = 8/);
    assert.match(cartActionBarSource, /const DRAG_SNAP_MIN_DISTANCE = 96/);
    assert.match(cartActionBarSource, /const DRAG_SNAP_PROGRESS = 0\.2/);
    assert.match(cartActionBarSource, /const getDragSnapDistance = \(\) => Math\.max\(/);
    assert.match(cartActionBarSource, /const handleHandlePointerDown = \(event: React\.PointerEvent<HTMLButtonElement>\) => \{[\s\S]*?const handleZone = event\.currentTarget[\s\S]*?handleZone\.setPointerCapture\(event\.pointerId\)/);
    assert.match(cartActionBarSource, /const handleHandlePointerMove = \(event: React\.PointerEvent<HTMLButtonElement>\) => \{\s*moveHandleDrag\(event\.clientY\);\s*\}/);
    assert.match(cartActionBarSource, /transition:\s*isPanelDragActive[\s\S]*?`height \$\{CART_ACTION_EXPAND_MS\}ms cubic-bezier\(0\.22, 1, 0\.36, 1\)`/s);
    assert.match(cartActionBarSource, /const scheduleDragOffset = \(nextOffset: number\)/);
    assert.match(cartActionBarSource, /dragUpdateFrameRef\.current = window\.requestAnimationFrame/);
    assert.match(cartActionBarSource, /onPointerDown=\{handleCollapsedPanelPointerDown\}/);
    assert.match(cartActionBarSource, /const handleCollapsedPanelPointerMove = \(event:[\s\S]*?\{\s*moveHandleDrag\(event\.clientY\);\s*\}/);
    assert.doesNotMatch(cartActionBarSource, /const handleCollapsedPanelPointerMove = \(event:[\s\S]{0,180}?isPanelExpandedPresentation/);
    assert.match(cartActionBarSource, /touchAction:\s*isExpanded \? 'pan-y' : 'pan-x'/);
});

test("cart handle also supports click fallback without double toggling pointer taps", () => {
    assert.match(cartActionBarSource, /const HANDLE_CLICK_GUARD_MS = 450/);
    assert.match(cartActionBarSource, /const handledPointerGesture = React\.useRef\(false\)/);
    assert.match(cartActionBarSource, /const handleHandleClick = \(\) => \{/);
    assert.match(cartActionBarSource, /if \(handledPointerGesture\.current\) return/);
    assert.match(cartActionBarSource, /setExpandedFromHandle\(isExpanded \? false : true\)/);
    assert.match(cartActionBarSource, /const beginHandleDrag = \(clientY: number\) => \{\s*if \(dragStartY\.current != null\) return;/);
    assert.match(cartActionBarSource, /if \(dragStartY\.current != null\) return;\s*dragStartY\.current = clientY/);
    assert.doesNotMatch(cartActionBarSource, /const beginHandleDrag = \(clientY: number\) => \{\s*setExpandedFromHandle\(true\)/);
    assert.match(cartActionBarSource, /const handleHandlePointerDown = \(event: React\.PointerEvent<HTMLButtonElement>\) => \{[\s\S]*?beginHandleDrag\(event\.clientY\)/);
    assert.doesNotMatch(cartActionBarSource, /const handleHandleMouseDown/);
    assert.doesNotMatch(cartActionBarSource, /const handleHandleTouchStart/);
    assert.doesNotMatch(cartActionBarSource, /const openFromHandleTarget = \(target: EventTarget \| null\) => \{/);
    assert.match(cartActionBarSource, /const handleZoneRef = React\.useRef<HTMLButtonElement \| null>\(null\)/);
    assert.doesNotMatch(cartActionBarSource, /handleZone\.addEventListener/);
    assert.doesNotMatch(cartActionBarSource, /handleZone\.addEventListener\('pointerdown', openHandleZone\)/);
    assert.doesNotMatch(cartActionBarSource, /handleZone\.addEventListener\('mousedown', openHandleZone\)/);
    assert.doesNotMatch(cartActionBarSource, /handleZone\.addEventListener\('touchstart', openHandleZone/);
    assert.doesNotMatch(cartActionBarSource, /const handleContentMouseDownCapture = \(event: React\.MouseEvent<HTMLDivElement>\) => \{/);
    assert.doesNotMatch(cartActionBarSource, /const handleContentTouchStartCapture = \(event: React\.TouchEvent<HTMLDivElement>\) => \{/);
    assert.doesNotMatch(cartActionBarSource, /const handleContentPointerDownCapture = \(event: React\.PointerEvent<HTMLDivElement>\) => \{/);
    assert.doesNotMatch(cartActionBarSource, /const handleContentClickCapture = \(event: React\.MouseEvent<HTMLDivElement>\) => \{/);
    assert.match(cartActionBarSource, /if \(!isDragging\.current\) \{/);
    assert.match(cartActionBarSource, /const setExpandedFromHandle = \(nextExpanded: boolean\) => \{/);
    assert.match(cartActionBarSource, /const setExpandedFromHandle = \(nextExpanded: boolean\) => \{[\s\S]*?dragStartY\.current = null;[\s\S]*?isDragging\.current = false;[\s\S]*?resetDragOffset\(\);/);
    assert.match(cartActionBarSource, /setIsExpanded\(nextExpanded\)/);
    assert.doesNotMatch(cartActionBarSource, /flushSync\(\(\) => \{/);
    assert.match(cartActionBarSource, /setExpandedFromHandle\(true\)/);
    assert.doesNotMatch(cartActionBarSource, /setIsExpanded\(prev => !prev\)/);
    assert.match(cartActionBarSource, /}, HANDLE_CLICK_GUARD_MS\)/);
    assert.match(cartActionBarSource, /className="relative z-10 flex flex-col items-center select-none"[\s\S]*?style=\{\{ paddingTop: 5, paddingBottom: 0 \}\}/);
    assert.match(cartActionBarSource, /<button\s+ref=\{handleZoneRef\}[\s\S]*?type="button"[\s\S]*?aria-label="Открыть корзину"[\s\S]*?className="cart-action-bar-handle-zone absolute left-0 right-0 top-0 z-10 h-\[36px\]/);
    assert.match(cartActionBarSource, /aria-expanded=\{isExpanded\}/);
    assert.match(cartActionBarSource, /style=\{\{ touchAction: 'none' \}\}/);
    assert.match(cartActionBarSource, /onPointerDown=\{handleHandlePointerDown\}/);
    assert.match(cartActionBarSource, /onPointerMove=\{handleHandlePointerMove\}/);
    assert.match(cartActionBarSource, /onPointerUp=\{handleHandlePointerUp\}/);
    assert.doesNotMatch(cartActionBarSource, /onMouseDown=\{handleHandleMouseDown\}/);
    assert.doesNotMatch(cartActionBarSource, /onTouchStart=\{handleHandleTouchStart\}/);
    assert.doesNotMatch(cartActionBarSource, /onPointerDownCapture=\{handleContentPointerDownCapture\}/);
    assert.doesNotMatch(cartActionBarSource, /onMouseDownCapture=\{handleContentMouseDownCapture\}/);
    assert.doesNotMatch(cartActionBarSource, /onTouchStartCapture=\{handleContentTouchStartCapture\}/);
    assert.doesNotMatch(cartActionBarSource, /onClickCapture=\{handleContentClickCapture\}/);
    assert.doesNotMatch(cartActionBarSource, /cart-action-bar-handle h-\[2px\][^"]*pointer-events-none/);
    assert.doesNotMatch(cartActionBarSource, /mt-\[2px\][^"]*pointer-events-none/);
    assert.match(cartActionBarSource, /onClick=\{handleHandleClick\}/);
});

test("collapsed product panel opens the expanded cart without hijacking inner controls", () => {
    assert.match(cartActionBarSource, /const handleCollapsedPanelClick = \(event: React\.MouseEvent<HTMLDivElement>\) => \{/);
    assert.match(cartActionBarSource, /const openCollapsedPanelTarget = \(target: EventTarget \| null\) => \{/);
    assert.match(cartActionBarSource, /if \(isPanelExpandedPresentation\) return/);
    assert.match(cartActionBarSource, /element\?\.closest\('\.cart-action-bar-product-summary'\)/);
    assert.match(cartActionBarSource, /element\?\.closest\('button, a, input, select, textarea, \[role="button"\]'\)/);
    assert.match(cartActionBarSource, /const handleCollapsedPanelPointerDown[\s\S]*?element\?\.closest\('button, a, input, select, textarea, \[role="button"\]'\)/);
    assert.match(cartActionBarSource, /setExpandedFromHandle\(true\)/);
    assert.doesNotMatch(cartActionBarSource, /productPanel\.addEventListener\('pointerdown', openCollapsedPanel\)/);
    assert.doesNotMatch(cartActionBarSource, /productPanel\.addEventListener/);
    assert.match(cartActionBarSource, /<button\s+type="button"\s+className="cart-action-bar-product-summary/);
    assert.match(cartActionBarSource, /aria-label="Раскрыть корзину"/);
    assert.doesNotMatch(cartActionBarSource, /onPointerDown=\{\(\) => setExpandedFromHandle\(true\)\}/);
    assert.match(cartActionBarSource, /onClick=\{\(\) => setExpandedFromHandle\(true\)\}/);
    assert.match(cartActionBarSource, /onClick=\{handleCollapsedPanelClick\}/);
    assert.match(cartActionBarSource, /onClickCapture=\{handleCollapsedPanelClickCapture\}/);
    assert.match(cartActionBarSource, /onPointerMove=\{handleCollapsedPanelPointerMove\}/);
});

test("cart details popup follows the Figma detailed product overlay", () => {
    assert.match(cartActionBarSource, /selectedDetailsItem/);
    assert.match(cartActionBarSource, /<CartItemDetailsPopup/);
    assert.match(cartActionBarSource, /cart-action-bar-details-popup/);
    assert.match(cartActionBarSource, /h-\[min\(416px,calc\(100dvh-32px\)\)\] w-\[min\(355px,calc\(100vw-16px\)\)\]/);
    assert.match(cartActionBarSource, /relative h-\[406px\] max-h-full overflow-hidden rounded-\[15px\]/);
    assert.match(cartActionBarSource, /grid h-full grid-cols-\[205px_minmax\(0,1fr\)\] gap-\[0px\] px-\[8px\] pb-\[8px\] pt-\[53px\]/);
    assert.match(cartActionBarSource, /cart-action-bar-details-images flex h-full flex-col items-center gap-\[0px\] overflow-hidden/);
    assert.match(cartActionBarSource, /cart-action-bar-details-image relative h-\[170px\] w-\[205px\] shrink-0/);
    assert.doesNotMatch(cartActionBarSource, /absolute bottom-\[0px\] left-\[-13px\]/);
    assert.match(cartActionBarSource, /min-w-0 pl-\[5px\] pr-\[5px\] font-manrope text-black/);
    assert.match(cartActionBarSource, /ИЗМЕНИТЬ/);
    assert.match(cartActionBarSource, /src="\/edit_icon\.svg"/);
    assert.doesNotMatch(cartActionBarSource, /GearSmallIcon color="#BBBBBB"/);
    assert.match(cartActionBarSource, /Дополнительные детали:/);
    assert.match(cartActionBarSource, /customization\?\.decorations/);
    assert.match(cartActionBarSource, /modelImages\.back/);
});

test("expanded cart footer starts the selected payment instead of opening legacy checkout", () => {
    assert.match(cartActionBarSource, /const \[paymentMethod, setPaymentMethod\] = useState<CartPaymentMethod>\('qr'\)/);
    assert.match(cartActionBarSource, /onSelect=\{\(\) => setPaymentMethod\('qr'\)\}/);
    assert.match(cartActionBarSource, /onSelect=\{\(\) => setPaymentMethod\('card'\)\}/);
    assert.equal((cartActionBarSource.match(/variant="payment"/g) ?? []).length, 2);
    assert.match(cartActionBarSource, /onClick=\{isPanelExpandedPresentation \? handleExpandedPayment : onBuy\}/);
    assert.match(cartActionBarSource, /payment_method:\s*paymentMethod/);
    assert.match(cartActionBarSource, /createCartActionOrder\(\{/);
    assert.match(cartActionBarSource, /requestJson<CartActionOrderResponse>\('\/orders'/);
    assert.match(cartActionBarSource, /const CART_ACTION_GUEST_PAYMENT_EMAIL = 'guest@garment-buro\.ru'/);
    assert.match(cartActionBarSource, /email:\s*user\?\.email\?\.trim\(\) \|\| CART_ACTION_GUEST_PAYMENT_EMAIL/);
    assert.doesNotMatch(cartActionBarSource, /if \(!isAuthenticated \|\| !user\?\.email\)/);
    assert.match(cartActionBarSource, /window\.location\.assign\(data\.payment_url\)/);
    assert.match(cartActionBarSource, /router\.push\(data\.order_id \? `\/order\/\$\{data\.order_id\}` : '\/order\/error'\)/);
    assert.match(cartActionBarSource, /isPanelExpandedPresentation[\s\S]*?'ОПЛАТИТЬ'[\s\S]*?: 'КУПИТЬ'/);
    assert.doesNotMatch(cartActionBarSource, /onClick=\{onBuy\}/);
    assert.match(cartActionBarSource, /const CART_ACTION_CONTENT_GLOW_EXPANDED_HEIGHT = '100px'/);
    assert.match(cartActionBarSource, /className="cart-action-bar-content-glow pointer-events-none absolute bottom-\[-30px\] left-0 z-0"/);
    assert.match(cartActionBarSource, /width:\s*'100%'/);
    assert.match(cartActionBarSource, /background:\s*isLiquidV2[\s\S]*?\? '#D5D5D5'[\s\S]*?: isPanelExpandedPresentation \? '#A2A2A2' : '#D5D5D5'/);
    assert.match(cartActionBarSource, /className="cart-action-bar-footer relative z-10 mb-\[7px\]/);
    assert.match(cartActionBarSource, /style=\{\{ marginTop: '9px' \}\}/);
    assert.match(cartActionBarSource, /const shouldCollapseFromFooter = isPanelExpandedPresentation && !pathname\?\.startsWith\('\/product\/'\)/);
    assert.match(cartActionBarSource, /onClick=\{shouldCollapseFromFooter \? \(\) => setExpandedFromHandle\(false\) : onEdit\}/);
    assert.match(cartActionBarSource, /src="\/back_icon_item\.svg"/);
    assert.match(cartActionBarSource, /shouldCollapseFromFooter \? 'НАЗАД' : 'ИЗМЕНИТЬ'/);
});
