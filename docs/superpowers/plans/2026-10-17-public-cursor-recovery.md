# Recover a public list after its cursor becomes invalid

- [x] Reproduce repeat of a rejected cursor in the production-built catalog.
- [x] Give invalid public cursors a stable API code distinct from input errors.
  Map it to a page-domain error at the API boundary, keeping generic HTTP
  transport independent of catalog state.
- [x] Keep visible cards on cursor failure and offer an explicit first-page
  refresh in clothing, people and communities. Prevent another append using a
  cursor known to be invalid; keep normal network/page retry unchanged.
- [x] Verify API codes, input validation, pagination cancellation/retry,
  production-built browser recovery, frontend checks and update the project map.
