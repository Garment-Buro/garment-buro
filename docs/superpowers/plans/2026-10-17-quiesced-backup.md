# Coordinated backup maintenance window

- [x] Serialize standalone backups with application deployment using the same
  inherited lock, without deadlocking the backup invoked by remote-deploy.
- [x] Record running services and refuse active one-shot setup/migration jobs
  before changing containers. Stop all application writers, then stop MinIO;
  require a clean storage exit before dumping or archiving.
- [x] Read legacy mounted data through a network-isolated read-only helper;
  never restart a stopped API merely to archive its data.
- [x] On success, archive failure or catchable interruption, restore only
  previously running services, with healthy storage before applications.
  Fail explicitly when service restoration fails.
- [x] Verify ordering, disabled services, partial failures, signals, concurrent
  invocations and inherited deployment locks. Repeat actual native recovery
  with the new script controlling the synthetic source MinIO lifecycle.
- [x] Update deployment/runtime documentation and the interactive project map
  with downtime behavior and precise limits of the evidence.

This is a maintenance-window procedure for deployment-managed writers and the
dedicated MinIO volume. Unmanaged clients/host jobs must be stopped separately.
Actual Docker execution, previous-image/schema compatibility, production-volume
restore and public payment/worker/webhook E2E remain release gates.

Evidence: 46 focused deployment tests, full Ruff and changed-file formatting,
bash syntax and diff checks. Native proof: 53 actual source writes before the
script stopped the writer and MinIO; one write after recovery. A separate
restore matched 106 tables, 10,000 orders, three object hashes and their DB
metadata, public/private access, API readiness/history/receipt and next ID10001.
Only Docker transport was emulated. Owned services/private fixtures were
removed and shared MinIO remained healthy. Eleven offline Chromium map checks
passed at 320/390/736; the backup flow screenshot was visually inspected.
