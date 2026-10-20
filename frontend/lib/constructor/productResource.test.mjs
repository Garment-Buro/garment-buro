import assert from "node:assert/strict";
import test from "node:test";
import { ConstructorProductResource } from "./productResource.ts";

const first = { id: 17, title: "Первая модель", price: 1000, variants: [] };
const deferred = () => {
  let resolve;
  const promise = new Promise((ok) => (resolve = ok));
  return { promise, resolve };
};
test("clearing the requested product immediately clears the previous usable model", async () => {
  const resource = new ConstructorProductResource();
  await resource.load("17", async () => first);
  assert.equal(resource.getSnapshot().product.id, 17);
  await resource.load(null, async () => {
    throw new Error("No request expected");
  });
  assert.equal(resource.getSnapshot().product, null);
  assert.equal(resource.getSnapshot().status, "idle");
  resource.dispose();
});
test("changing the product hides the old model during loading and after a failed read", async () => {
  const resource = new ConstructorProductResource(),
    pending = deferred();
  await resource.load("17", async () => first);
  const next = resource.load("18", async () => pending.promise);
  assert.equal(resource.getSnapshot().product, null);
  assert.equal(resource.getSnapshot().status, "loading");
  pending.resolve({ ...first, id: 18, title: "Вторая модель" });
  await next;
  assert.equal(resource.getSnapshot().product.id, 18);
  const error = Object.assign(new Error("Unavailable"), { status: 404 });
  await resource.load("19", async () => {
    throw error;
  });
  assert.equal(resource.getSnapshot().product, null);
  assert.equal(resource.getSnapshot().error, error);
  resource.dispose();
});
test("obsolete and mismatched product responses cannot supply a usable model", async () => {
  const resource = new ConstructorProductResource(),
    pending = deferred();
  let signal;
  const old = resource.load("17", async (_, value) => {
    signal = value;
    return pending.promise;
  });
  await resource.load("18", async () => ({ ...first, id: 18 }));
  assert.equal(signal.aborted, true);
  pending.resolve(first);
  await old;
  assert.equal(resource.getSnapshot().product.id, 18);
  await resource.load("19", async () => first);
  assert.equal(resource.getSnapshot().product, null);
  assert.ok(resource.getSnapshot().error instanceof Error);
  resource.dispose();
});
test("malformed identifiers never start a request and retry does not reuse failed data", async () => {
  const resource = new ConstructorProductResource();
  let requests = 0;
  for (const id of ["0", "-1", "NaN", "1.5", "17/secret", "2147483648"]) {
    await resource.load(id, async () => {
      requests++;
      return first;
    });
    assert.ok(resource.getSnapshot().error instanceof RangeError);
    assert.equal(resource.getSnapshot().product, null);
  }
  assert.equal(requests, 0);
  await resource.load("17", async () => {
    throw new TypeError("Offline");
  });
  await resource.load("17", async () => first);
  assert.equal(resource.getSnapshot().product.id, 17);
  assert.equal(resource.getSnapshot().error, null);
  resource.dispose();
});
