import assert from "node:assert/strict";
import test from "node:test";

import {
    buildConstructorCustomization,
    chunkArray,
    createDefaultFit,
    getFirstAvailableSize,
    getModelBounds,
    getProductImageList,
    versionConstructorMedia,
} from "./constructor.ts";

test("constructor media selects the first populated source and versions uploads", () => {
    const product = { id: 1, title: "Test", price: 100, mobile_slider_images: "/a.webp, /b.webp" };
    assert.deepEqual(getProductImageList(product), ["/a.webp", "/b.webp"]);
    assert.match(versionConstructorMedia("/uploads/model.webp"), /^\/uploads\/model\.webp\?v=/);
    assert.equal(versionConstructorMedia("/mock/model.webp"), "/mock/model.webp");
});

test("constructor customization is built in the domain layer", () => {
    const customization = buildConstructorCustomization({
        selectedModel: {
            id: "product_1",
            name: "Test",
            src: "/model-front.webp",
            price: 5000,
        },
        selectedSize: "M",
        selectedFit: null,
        garmentDimensions: { widthCm: 58, heightCm: 70 },
        placedItemsByView: {
            front: [{ uid: "item_1", variantId: "print_1", x: 400, y: 350, scale: 1, rotation: 12 }],
            back: [],
        },
        hardwareMap: {
            print_1: {
                id: "print_1",
                categoryId: "prints",
                name: "Print",
                src: "/mock/prints/1.webp",
                price: 300,
                defaultWidth: 80,
                defaultHeight: 60,
            },
        },
        frontImage: "/model-front.webp",
        backImage: "/model-back.webp",
        totalPrice: 5300,
        comment: "test",
    });

    assert.equal(customization?.kind, "constructor");
    assert.equal(customization?.modelImages.back, "/model-back.webp");
    assert.equal(customization?.decorations[0].variantId, "print_1");
    assert.equal(customization?.decorations[0].rotation, 12);
    assert.equal(customization?.totalPrice, 5300);
});

test("constructor fit and bounds stay normalized", () => {
    const fit = createDefaultFit("M", { widthCm: 1, heightCm: 1 });
    assert.equal(fit.selectedSize, "M");
    assert.ok(fit.widthCm >= fit.widthRange.min);
    assert.ok(fit.lengthCm >= fit.lengthRange.min);
    assert.deepEqual(getModelBounds({ widthCm: 80, heightCm: 80 }), { x: 0, y: 0, width: 800, height: 800 });
});

test("constructor size and paging helpers preserve ordering", () => {
    const product = {
        id: 1,
        title: "Test",
        price: 100,
        variants: [{ id: 1, size: "S", color: "black", stock_quantity: 0 }, { id: 2, size: "L", color: "black", stock_quantity: 2 }],
    };
    assert.equal(getFirstAvailableSize(product), "L");
    assert.deepEqual(chunkArray([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]]);
});
