import assert from "node:assert/strict";
import test from "node:test";
import { nextConstructorLifetime } from "./lifetime.ts";

test("first login adopts guest work and token rotation keeps the authenticated canvas", () => {
  const guest = { account: null, revision: 0 };
  const loggedIn = nextConstructorLifetime(guest, "one:epoch-a");
  assert.deepEqual(loggedIn, { account: "one:epoch-a", revision: 0 });
  assert.equal(nextConstructorLifetime(loggedIn, "one:epoch-a"), loggedIn);
});
test("logout, a different account and a new login lifetime revoke the old canvas", () => {
  const first = { account: "one:epoch-a", revision: 0 };
  for (const next of [null, "two:epoch-b", "one:epoch-new"])
    assert.deepEqual(nextConstructorLifetime(first, next), {
      account: next,
      revision: 1,
    });
  const signedOut = nextConstructorLifetime(first, null);
  assert.deepEqual(nextConstructorLifetime(signedOut, "two:epoch-b"), {
    account: "two:epoch-b",
    revision: 1,
  });
});
