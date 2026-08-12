import assert from "node:assert/strict";
import test from "node:test";

import {
    canPanStage,
    getStagePanBounds,
    getVisibleCanvasHeight,
    getCustomDecorationScaleLimits,
    getNextDecorationDropPosition,
    getPanelSwipeAction,
    shouldDeferHardwareSelection,
} from "../../lib/constructor/utils/interaction.ts";

test("garment can only pan after the canvas is zoomed beyond fitted scale", () => {
    assert.equal(canPanStage(0.75, 0.75), false);
    assert.equal(canPanStage(0.755, 0.75), false);
    assert.equal(canPanStage(0.8, 0.75), true);
});

test("garment is fitted into the area above constructor controls", () => {
    assert.equal(getVisibleCanvasHeight(800, 213), 587);
    assert.equal(getVisibleCanvasHeight(180, 240), 1);
});

test("zoomed garment edges can be moved to the center of the visible canvas", () => {
    assert.deepEqual(getStagePanBounds({
        containerWidth: 400,
        containerHeight: 800,
        bottomInset: 200,
        scale: 2,
        bounds: { x: 100, y: 150, width: 600, height: 500 },
    }), {
        minX: -1200,
        maxX: 0,
        minY: -1000,
        maxY: 0,
    });
});

test("selecting another decoration is deferred while one is already active", () => {
    assert.equal(shouldDeferHardwareSelection("item-1", "item-2"), true);
    assert.equal(shouldDeferHardwareSelection("item-1", "item-1"), false);
    assert.equal(shouldDeferHardwareSelection(null, "item-2"), false);
});

test("new decorations drop near the center without stacking on existing ones", () => {
    const centerPoint = { x: 500, y: 420 };
    const first = getNextDecorationDropPosition({
        centerPoint,
        existingItems: [],
    });
    const second = getNextDecorationDropPosition({
        centerPoint,
        existingItems: [{ uid: "item_1", variantId: "print", x: first.x, y: first.y, scale: 1 }],
    });
    const third = getNextDecorationDropPosition({
        centerPoint,
        existingItems: [
            { uid: "item_1", variantId: "print", x: first.x, y: first.y, scale: 1 },
            { uid: "item_2", variantId: "print", x: second.x, y: second.y, scale: 1 },
        ],
    });

    assert.deepEqual(first, centerPoint);
    assert.notDeepEqual(second, first);
    assert.notDeepEqual(third, first);
    assert.notDeepEqual(third, second);
    assert.ok(Math.hypot(second.x - first.x, second.y - first.y) >= 72);
    assert.ok(Math.hypot(third.x - second.x, third.y - second.y) >= 72);
});

test("custom uploaded photos cannot be scaled below 100%", () => {
    const limits = getCustomDecorationScaleLimits({
        isCustom: true,
        minScale: 0.08,
        maxScale: 3,
    });

    assert.equal(limits.min, 1);
    assert.equal(limits.max, 3);
});

test("existing non-custom hardware keeps its own minimum scale", () => {
    const limits = getCustomDecorationScaleLimits({
        isCustom: false,
        minScale: 0.25,
        maxScale: 4,
    });

    assert.equal(limits.min, 0.25);
    assert.equal(limits.max, 4);
});

test("collapsed panel expands on an upward swipe", () => {
    assert.equal(getPanelSwipeAction({
        isExpanded: false,
        deltaX: 4,
        deltaY: -48,
    }), "expand");
});

test("expanded panel collapses on a downward swipe", () => {
    assert.equal(getPanelSwipeAction({
        isExpanded: true,
        deltaX: 3,
        deltaY: 52,
    }), "collapse");
});
