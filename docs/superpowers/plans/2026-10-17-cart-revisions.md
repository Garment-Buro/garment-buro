# Revisioned persistent carts

- [x] Reproduce stale writes succeeding under the client-clock protocol.
- [x] Replace runtime clock ordering with a server-generated opaque revision,
  expected revision and a durable operation ID/digest for exact replay. Preserve
  legacy import as a separate offline boundary. Add reversible migration0068.
- [x] Read before writing, retain dirty edits and a pending immutable request
  across reloads, and apply server-confirmed prices. Never silently rebase a
  conflicting edit. Offer explicit server/local conflict choices in both cart UIs.
- [x] Verify real PostgreSQL concurrent writes, expiry/recreation, replay,
  migration roundtrip/schema agreement, frontend state/API/build and multi-tab
  browser behavior with the real API. Refresh the map and release journal.

Release remains coordinated: old browser clients without the new write contract
must not keep writing. A stale or unknown version must fail, not fall back to
client timestamps. Empty snapshots participate in the same revision protocol.
The unused unversioned DELETE API will be removed; clear uses a versioned empty PUT.
Cart tokens remain guest capabilities, separate from account/profile data.
