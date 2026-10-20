import assert from "node:assert/strict";
import test from "node:test";
import {
    ConstructorPriceResource,
    constructorPriceRequest,
    currentPriceQuote,
    priceRequestKey,
} from "./priceResource.ts";

const input = { productId: 7, decorations: [{ uid: "a", scale: 1 }] };
const quote = (request, price = 80) => ({
    product_id: request.productId,
    policy_revision: "custom-scale-v1",
    decoration_base_price: "80",
    base_price: "100.25",
    customization_price: String(price),
    total_price: String(100.25 + price),
    decorations: request.decorations.map((d) => ({ uid: d.uid, price: String(price) })),
});
const deferred = () => {
    let resolve;
    const promise = new Promise((ok) => (resolve = ok));
    return { resolve, promise };
};

test("changing scales hides old prices synchronously and obsolete replies cannot publish", async () => {
    const resource = new ConstructorPriceResource();
    await resource.load(input, async (value) => quote(value), 0);
    assert.equal(currentPriceQuote(resource.getSnapshot(), input).totalPrice, 180.25);
    const next = { ...input, decorations: [{ uid: "a", scale: 1.5 }] };
    assert.equal(currentPriceQuote(resource.getSnapshot(), next), null);
    const held = deferred();
    let signal;
    const pending = resource.load(
        next,
        async (_, s) => {
            signal = s;
            return held.promise;
        },
        0,
    );
    assert.equal(resource.getSnapshot().quote, null);
    const other = { ...input, productId: 8 };
    await resource.load(other, async (value) => quote(value), 0);
    assert.equal(signal.aborted, true);
    held.resolve(quote(next, 120));
    await pending;
    assert.equal(resource.getSnapshot().quote.productId, 8);
    resource.dispose();
});

test("a burst of edits issues only the last bounded request and disposal cancels timers", async () => {
    const resource = new ConstructorPriceResource();
    const sent = [];
    const transport = async (value) => {
        sent.push(value);
        return quote(value);
    };
    const first = resource.load(input, transport, 20);
    const next = { ...input, decorations: [{ uid: "a", scale: 1.2 }] };
    const second = resource.load(next, transport, 20);
    await Promise.all([first, second]);
    assert.deepEqual(sent, [next]);
    const canceled = resource.load(input, transport, 20);
    resource.dispose();
    await canceled;
    assert.equal(sent.length, 1);
});

test("error and malformed replies never authorize a purchase and retry obtains a fresh quote", async () => {
    const resource = new ConstructorPriceResource();
    await resource.load(
        input,
        async () => {
            throw new TypeError("Offline");
        },
        0,
    );
    assert.equal(currentPriceQuote(resource.getSnapshot(), input), null);
    assert.equal(resource.getSnapshot().status, "error");
    for (const invalid of [
        { ...quote(input), product_id: 8 },
        { ...quote(input), decorations: [{ uid: "other", price: 80 }] },
        { ...quote(input), total_price: "100.25" },
        { ...quote(input), decorations: [{ uid: "a", price: -1 }] },
    ]) {
        await resource.load(input, async () => invalid, 0);
        assert.equal(resource.getSnapshot().status, "error");
        assert.equal(currentPriceQuote(resource.getSnapshot(), input), null);
    }
    await resource.load(input, async (value) => quote(value, 120), 0);
    assert.equal(currentPriceQuote(resource.getSnapshot(), input).totalPrice, 220.25);
    await resource.load(
        null,
        async () => {
            throw new Error("No request expected");
        },
        0,
    );
    assert.equal(resource.getSnapshot().status, "idle");
    assert.equal(resource.getSnapshot().quote, null);
});

test("positions, rotation and comments do not affect the compact pricing fingerprint; both views do", () => {
    const placement = { uid: "a", variantId: "custom", x: 10, y: 20, rotation: 0, scale: 1 };
    const first = constructorPriceRequest(7, { front: [placement], back: [] });
    const moved = constructorPriceRequest(7, { front: [{ ...placement, x: 200, rotation: 90 }], back: [] });
    assert.equal(priceRequestKey(first), priceRequestKey(moved));
    assert.deepEqual(first, input);
    assert.deepEqual(
        constructorPriceRequest(7, { front: [placement], back: [{ ...placement, uid: "b", scale: 2 }] }).decorations,
        [
            { uid: "a", scale: 1 },
            { uid: "b", scale: 2 },
        ],
    );
    assert.equal(constructorPriceRequest(null, { front: [], back: [] }), null);
});
