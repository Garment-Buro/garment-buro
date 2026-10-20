# Customization pricing

User decision: retain 80 RUB and the current scale-based rule, with one place to change the formula later. People/public profiles and communities/collection landings remain separate.

Each placed custom print or text costs `max(80, round_half_up(80 * scale))` RUB. The existing editor's baseline long side is its unscaled long side; their ratio is scale. Count each placement, including the back. Product base price comes from canonical Product. Quantity and delivery are applied by the existing order service. There is no real hardware tariff catalog; do not reactivate mock hardware prices.

One server policy calculates previews and final order snapshots. A small public preview request contains placement IDs/scales, not images or text. Debounce scale changes, cancel obsolete reads and hide obsolete prices synchronously. No cart purchase until the current preview succeeds; failure has an explicit retry. Position, rotation and comments do not reprice. Saved project prices remain previews and are recomputed when opened.

Cart persistence remains a recoverable draft snapshot, not a payment authorization. Constructor lines written to the cart use the same server policy, batched Product reads; legacy import is a historical snapshot. Checkout independently recalculates and retains its existing pre-order409 explicit price confirmation, idempotency, delivery proof, inventory reservation and payment recovery. Never change prices of an existing accepted order or replay.

Malformed constructor placement input is rejected before cart/order writes. Bound scales/count/IDs and reject duplicate placement IDs, bool/nonfinite/negative scales. Ignore supplied prices. Preserve the rest of the customization snapshot and overwrite its price fields with the server result when stored in new carts/orders. Retain existing unrelated legacy metadata compatibility.

No new dependency, database table, admin screen, stage/commit/push/deploy. Preserve all previous dirty-tree work. Local verification and the offline architecture map must distinguish this result from a production release.
