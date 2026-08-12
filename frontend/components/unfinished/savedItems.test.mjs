import assert from "node:assert/strict";
import test from "node:test";

import {
    CONSTRUCTOR_DRAFTS_STORAGE_KEY,
    MY_COLLECTION_STORAGE_KEY,
    buildSavedProfileItem,
    loadConstructorDraft,
    parseSavedProfileItems,
    saveConstructorDraft,
    serializeSavedProfileItems,
} from "../../lib/unfinished/utils/savedItems.ts";

const createDraftState = () => ({
    activeView: "front",
    canvasPixelSize: { width: 640, height: 640 },
    modelBounds: { x: 90, y: 70, width: 460, height: 520 },
    customization: {
        kind: "constructor",
        selectedSize: "M",
        modelImages: {
            front: "/uploads/front.png",
            back: "/uploads/back.png",
        },
        canvas: { widthCm: 100, heightCm: 100 },
        garment: { widthCm: 58, heightCm: 70 },
        decorations: [{
            view: "front",
            uid: "item_1",
            variantId: "print_1",
            name: "print",
            price: 300,
            image: "/mock/prints/1.webp",
            widthCm: 20,
            heightCm: 14,
            x: 320,
            y: 280,
            scale: 1,
            rotation: 0,
        }],
        totalPrice: 5300,
    },
});

test("saved profile items have stable storage keys", () => {
    assert.equal(CONSTRUCTOR_DRAFTS_STORAGE_KEY, "plus2opacity-constructor-drafts");
    assert.equal(MY_COLLECTION_STORAGE_KEY, "plus2opacity-my-collection");
});

test("constructor drafts serialize as numbered profile items", () => {
    const item = buildSavedProfileItem({
        kind: "draft",
        index: 2,
        productId: 27,
        title: "bag: swamp",
        imageSrc: "/uploads/swamp.png",
        savedAt: 1783188000000,
    });

    assert.deepEqual(item, {
        id: "draft-1783188000000-27",
        kind: "draft",
        number: "003",
        name: "bag: swamp",
        imageSrc: "/uploads/swamp.png",
        productId: 27,
        savedAt: 1783188000000,
    });

    assert.deepEqual(parseSavedProfileItems(serializeSavedProfileItems([item])), [item]);
});

test("stored profile items discard malformed entries", () => {
    const validItem = buildSavedProfileItem({
        kind: "collection",
        index: 0,
        productId: 8,
        title: "hat: love & murder",
        imageSrc: "/mock/hoodie.webp",
        savedAt: 1783188000000,
    });

    assert.deepEqual(parseSavedProfileItems(JSON.stringify([null, { id: 12 }, validItem])), [validItem]);
    assert.deepEqual(parseSavedProfileItems("not json"), []);
});

test("constructor draft state survives storage validation", () => {
    const item = buildSavedProfileItem({
        kind: "draft",
        index: 0,
        productId: 27,
        title: "custom garment",
        imageSrc: "/uploads/front.png",
        savedAt: 1783188000000,
        draftState: createDraftState(),
    });

    const [parsedItem] = parseSavedProfileItems(serializeSavedProfileItems([item]));
    assert.deepEqual(parsedItem.draftState, item.draftState);
});

test("saveConstructorDraft prepends a draft to localStorage", () => {
    const storage = new Map();
    const previousWindow = globalThis.window;

    globalThis.window = {
        localStorage: {
            getItem: (key) => storage.get(key) ?? null,
            setItem: (key, value) => storage.set(key, String(value)),
        },
    };

    try {
        saveConstructorDraft({
            productId: 11,
            title: "bag: swamp",
            imageSrc: "/uploads/bag.png",
        });
        const secondDraft = saveConstructorDraft({
            productId: 12,
            title: "hat: love & murder",
            imageSrc: "/uploads/hat.png",
        });

        const savedItems = parseSavedProfileItems(storage.get(CONSTRUCTOR_DRAFTS_STORAGE_KEY));
        assert.equal(savedItems.length, 2);
        assert.equal(savedItems[0].id, secondDraft.id);
        assert.equal(savedItems[0].number, "002");
        assert.equal(savedItems[1].number, "001");
    } finally {
        globalThis.window = previousWindow;
    }
});

test("saving an existing draft updates it without creating a duplicate", () => {
    const storage = new Map();
    const previousWindow = globalThis.window;
    globalThis.window = {
        localStorage: {
            getItem: (key) => storage.get(key) ?? null,
            setItem: (key, value) => storage.set(key, String(value)),
        },
    };

    try {
        const initialDraft = saveConstructorDraft({
            productId: 27,
            title: "custom garment",
            imageSrc: "/uploads/front.png",
            draftState: createDraftState(),
        });
        const updatedDraft = saveConstructorDraft({
            draftId: initialDraft.id,
            productId: 27,
            title: "updated garment",
            imageSrc: "/uploads/back.png",
            draftState: {
                ...createDraftState(),
                activeView: "back",
            },
        });

        assert.equal(updatedDraft.id, initialDraft.id);
        assert.equal(updatedDraft.number, initialDraft.number);
        assert.equal(loadConstructorDraft(initialDraft.id)?.name, "updated garment");
        assert.equal(parseSavedProfileItems(storage.get(CONSTRUCTOR_DRAFTS_STORAGE_KEY)).length, 1);
    } finally {
        globalThis.window = previousWindow;
    }
});
