# Truthful customer order states

The order popup currently renders success for every non-cancelled order,
including unpaid orders. History omits awaiting-payment, cancelled and attention
workflow labels. The tracking button has no action, and the old error bookmark
asserts that no order exists without checking the server.

- [x] Cover every workflow state with a customer-safe server label, preserving
  unknown/absent workflow compatibility and existing business transitions.
- [x] Share customer status/payment presentation between the order popup and
  both history views; never imply payment from checkout success or a URL.
- [x] Add explicit status refresh, show pending state during that request and
  retain account/abort isolation. Remove the inert tracking action and display
  only shipment data actually returned by the server.
- [x] Correct the unchecked error bookmark and payment-review explanation.
- [x] Verify state matrices, rendered markup, focused backend contracts, full
  frontend checks and actual browser interactions; document local-only scope.

Payment creation/capture/retry rules, accepted prices, order ownership and
provider integration remain server responsibilities. Do not create a new
payment attempt from the status refresh action.
