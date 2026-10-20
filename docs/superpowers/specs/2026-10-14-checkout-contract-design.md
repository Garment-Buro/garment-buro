# Modern checkout contract

The current frontend sends cart_items/total_price and no idempotency header;
the modular API expects items/claimed_total_price and an authenticated or guest
actor. Two forms also disagree about quote cancellation and retry. Orders
currently reprice goods but accept a browser-supplied shipping amount.

## Server delivery boundary

Use the existing CDEK quote endpoint and PostgreSQL catalog/directory. A quote
contains a short-lived signed proof of the amount and a hash of its complete
delivery request: canonical destination, method, quantities, trusted catalog
logistics and configured sender/tariff. No address or contact is embedded in the
proof. HMAC signing uses a purpose-derived server key, never an identity token.
Fifteen minutes is the quote validity window; persisted orders keep their price.

Pickup city/address comes from a directory snapshot no older than seven days,
not browser labels. Courier delivery requires an explicit city/address; no
invented Moscow or free-delivery fallback. Provider I/O happens after closing
the quote read transaction. Issuing a quote does not reserve inventory or create
an order.

Checkout validates the proof after acquiring its creation request and checking
for a completed replay, before persisting a new order. Verification repeats
only local preparation; it never calls the provider under row locks. A changed
address, quantity, logistics, tariff, price, signature or expired proof cannot
create an order. Exact replay of a persisted order succeeds after quote expiry
or directory outage without recomputing its price. Missing proof is rejected;
the removed legacy API is not an alternative.

## Client and contacts

Both forms will use one typed submission boundary and one pending-operation
controller. Preserve idempotency key, guest capability and original quote across
uncertain responses. Bound the operation to account and semantic payload; never
retry an uncertain purchase under a new key or silently substitute changed data.
Keep tokens out of URLs/logs. Clear the cart only when the durable order exists.

Store buyer name/phone and recipient email in the order alongside existing
receipt email and delivery contact snapshots. Buyer email is for receipt;
ownership remains bound to the verified actor or guest capability. Neither
submitted contact grants account access. Existing historical
rows remain nullable. Guest order access uses the existing hashed capability;
sign-in and account claim still require actual verified identity.

## Completion evidence

Behavioral proof of tampering rejection, canonical pickup, expiry and persisted
replay; actual HTTP quote → order → payment with transport doubles; two forms
using the same typed payload; lost response/reload/account-change retry; real
PostgreSQL concurrency and rollback; browser scenarios for guest/auth, pickup/
courier and both entrypoints. Full lint/tests/build/review and existing release
gates remain necessary. A signed quote alone does not prove a complete purchase.
