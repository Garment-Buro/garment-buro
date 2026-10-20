import assert from "node:assert/strict";
import test from "node:test";
import { readUploadedImage } from "./imageInput.ts";

function browser(t) {
  const resources = {reader: undefined, image: undefined, aborts: 0};
  const install = (key, value) => {
    const previous = Object.getOwnPropertyDescriptor(globalThis, key);
    Object.defineProperty(globalThis, key, {
      value,
      configurable: true,
      writable: true,
    });
    t.after(() => {
      if (previous) Object.defineProperty(globalThis, key, previous);
      else delete globalThis[key];
    });
  };
  install(
    "FileReader",
    class {
      result = "data:image/png;base64,AAAA";
      error = null;
      readAsDataURL() {
        resources.reader = this;
      }
      abort() {
        resources.aborts++;
      }
    },
  );
  install(
    "Image",
    class {
      naturalWidth = 20;
      naturalHeight = 30;
      constructor() {
        resources.image = this;
      }
      set src(value) {
        this.source = value;
      }
      get src() {
        return this.source;
      }
    },
  );
  return resources;
}
test("local raster reads validate the same formats and byte limit as project persistence before allocating a decoder", async (t) => {
  const fixture = browser(t);
  for (const file of [
    new File(["gif"], "bad.gif", { type: "image/gif" }),
    new File(["svg"], "bad.svg", { type: "image/svg+xml" }),
    new File([new Uint8Array(8 * 1024 * 1024 + 1)], "large.png", {
      type: "image/png",
    }),
  ])
    await assert.rejects(readUploadedImage(file), RangeError);
  assert.equal(fixture.reader, undefined);
});
test("a canceled local read aborts FileReader and cannot continue to image decode", async (t) => {
  const fixture = browser(t),
    controller = new AbortController();
  const read = readUploadedImage(
    new File(["png"], "a.png", { type: "image/png" }),
    controller.signal,
  );
  const loaded = fixture.reader.onload;
  controller.abort();
  await assert.rejects(read, { name: "AbortError" });
  assert.equal(fixture.aborts, 1);
  loaded();
  assert.equal(fixture.image, undefined);
});
test("cancellation while decoding clears the source and suppresses late success", async (t) => {
  const fixture = browser(t),
    controller = new AbortController();
  const read = readUploadedImage(
    new File(["png"], "a.png", { type: "image/png" }),
    controller.signal,
  );
  fixture.reader.onload();
  const loaded = fixture.image.onload;
  controller.abort();
  await assert.rejects(read, { name: "AbortError" });
  loaded();
  assert.equal(fixture.image.src, "");
});
test("a successful local decode returns dimensions and tears down event handlers", async (t) => {
  const fixture = browser(t);
  const read = readUploadedImage(
    new File(["png"], "a.png", { type: "image/png" }),
  );
  fixture.reader.onload();
  fixture.image.onload();
  assert.deepEqual(await read, {
    src: "data:image/png;base64,AAAA",
    width: 20,
    height: 30,
  });
  assert.equal(fixture.reader.onload, null);
  assert.equal(fixture.image.onload, null);
});

test("decoded images beyond the persisted dimensions are rejected before entering the canvas", async (t) => {
  const fixture = browser(t);
  for (const [width, height] of [
    [8193, 20],
    [5000, 5000],
  ]) {
    const read = readUploadedImage(
      new File(["png"], "a.png", { type: "image/png" }),
    );
    fixture.reader.onload();
    fixture.image.naturalWidth = width;
    fixture.image.naturalHeight = height;
    fixture.image.onload();
    await assert.rejects(read, RangeError);
  }
});
