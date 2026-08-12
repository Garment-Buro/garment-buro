import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const source = fs.readFileSync(
    path.join(root, "components", "cart", "CartActionBarV2.tsx"),
    "utf8",
);
const collapsedSource = fs.readFileSync(
    path.join(root, "components", "cart", "CartActionBarV2Collapsed.tsx"),
    "utf8",
);
const styles = fs.readFileSync(
    path.join(root, "components", "cart", "CartActionBarV2.module.css"),
    "utf8",
);
const actionBarSource = fs.readFileSync(
    path.join(root, "components", "cart", "CartActionBar.tsx"),
    "utf8",
);
const controllerSource = fs.readFileSync(
    path.join(root, "hooks", "cart", "useCartActionBarController.ts"),
    "utf8",
);

test("CartActionBarV2 stays visible while retaining the shared expandable cart", () => {
    assert.match(source, /"visible" \| "allowEmptyExpand" \| "collapsedVariant" \| "liquidV2Shifted"/);
    assert.match(source, /visible[\s\S]*?allowEmptyExpand[\s\S]*?collapsedVariant="liquid-v2"[\s\S]*?liquidV2Shifted=\{hasPassedShiftTrigger\}/);
    assert.match(actionBarSource, /cart-action-bar-overlay[\s\S]*?display:\s*isLiquidV2 \? 'block' : undefined/);
    assert.match(actionBarSource, /cart-action-bar-shell[\s\S]*?display:\s*isLiquidV2 \? 'block' : undefined/);
});

test("CartActionBarV2 moves the liquid divider as the supplied section passes above the cart", () => {
    assert.match(source, /document\.getElementById\(shiftAfterElementId\)/);
    assert.match(source, /const SHIFT_TRIGGER_BOTTOM_OFFSET = 64/);
    assert.match(source, /triggerElement\.getBoundingClientRect\(\)\.bottom[\s\S]*?<= window\.innerHeight - SHIFT_TRIGGER_BOTTOM_OFFSET/);
    assert.match(source, /liquidV2Shifted=\{hasPassedShiftTrigger\}/);
    assert.doesNotMatch(source, /hasCartItems|useCartStore/);
    assert.match(collapsedSource, /shifted \? Math\.min\(width \* 0\.42, 160\) : width \* 0\.785/);
    assert.match(collapsedSource, /const depth = height \* \(0\.12 \+ deformation \* 0\.1\)/);
    assert.match(collapsedSource, /distance \* 0\.021/);
    assert.match(collapsedSource, /velocityXRef\.current \*= 0\.76/);
    assert.match(collapsedSource, /const isSettled = \(/);
    assert.match(collapsedSource, /if \(animationFrame\) return/);
    assert.match(collapsedSource, /src="\/logo_anim_cart\.mp4"/);
    assert.doesNotMatch(collapsedSource, /pointerenter|pointermove|mouseenter|mousemove/i);
});

test("CartActionBarV2 keeps the item count before shifting and shows the presentation CTA after shifting", () => {
    assert.match(collapsedSource, /Корзина \(\{totalQuantity\}\)/);
    assert.match(collapsedSource, /className=\{styles\.combined\}[\s\S]*?onClick=\{onLogin\}[\s\S]*?Узнать о нас больше/);
    assert.doesNotMatch(collapsedSource, /displayTitle|combinedText/);
    assert.doesNotMatch(actionBarSource, /<CartActionBarV2Collapsed[\s\S]*?displayTitle=/);
});

test("CartActionBarV2 uses the supplied image as SVG content and keeps the exact collapsed geometry", () => {
    assert.match(collapsedSource, /<image[\s\S]*?href="\/cartv2_bg\.png"/);
    assert.doesNotMatch(collapsedSource + styles, /background-image|backgroundImage/);
    assert.match(styles, /\.root\s*\{[\s\S]*?height:\s*45px/);
    assert.match(styles, /\.logo\s*\{[\s\S]*?width:\s*35px;[\s\S]*?height:\s*35px/);
    assert.match(styles, /\.brandName\s*\{[\s\S]*?color:\s*#646464;[\s\S]*?font-size:\s*12px;[\s\S]*?font-weight:\s*600;[\s\S]*?line-height:\s*108\.187%/);
    assert.match(styles, /\.login,[\s\S]*?\.cart,[\s\S]*?\.combined\s*\{[\s\S]*?font-size:\s*12px/);
    assert.match(styles, /\.combined\s*\{[\s\S]*?pointer-events:\s*none/);
    assert.match(styles, /\.root\[data-cart-v2-shifted="true"\] \.combined\s*\{[\s\S]*?pointer-events:\s*auto/);
    assert.match(controllerSource, /collapsedHeight:\s*collapsedVariant === 'liquid-v2' \? 45 : undefined/);
    assert.match(actionBarSource, /height:\s*isLiquidV2 \? 3 : 2/);
    assert.match(actionBarSource, /background:\s*isLiquidV2[\s\S]*?\? '#D5D5D5'[\s\S]*?: isPanelExpandedPresentation \? '#A2A2A2' : '#D5D5D5'/);
    assert.match(actionBarSource, /boxShadow:\s*'0 0\.5px 0\.5px 0 rgba\(0, 0, 0, 0\.25\) inset'/);
    assert.match(actionBarSource, /isLiquidV2[\s\S]*?boxShadow:\s*'none'/);
    assert.match(actionBarSource, /backgroundColor:\s*isLiquidV2[\s\S]*?\? isPanelExpandedPresentation \? 'rgb\(255 255 255 \/ 80%\)' : 'transparent'/);
    assert.match(actionBarSource, /opacity:\s*isLiquidV2 \? 0\.74 : 1/);
    assert.match(actionBarSource, /isLiquidV2 \|\| !isPanelExpandedPresentation[\s\S]*?\? 'none'/);
});
