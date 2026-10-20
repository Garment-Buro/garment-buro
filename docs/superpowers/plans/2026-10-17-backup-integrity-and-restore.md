# Release backup integrity and restore rehearsal

Container execution is currently unavailable locally (broken OrbStack Docker
symlink); SSH to the configured server timed out. Do not count native or
transport checks as a container release/rollback proof.

- [x] Ensure two backups in the same second never overwrite each other.
- [x] Include deployment metadata in the checksum manifest and publish the
  completion manifest atomically only after all archives pass basic checks.
- [x] Add a read-only verifier for the complete bundle: exact allowlisted
  entries, hashes, private permissions, PostgreSQL magic and safe readable tar
  members. Do not source saved environment/release files or extract archives.
- [x] Rehearse actual PostgreSQL dump/restore and MinIO volume restore using
  isolated native services and synthetic records; check schema, content and
  public/private access after recovery. Preserve shared/user services.
- [x] Run focused deployment tests, document evidence and remaining container,
  live-volume consistency, previous-image and production-sized recovery gates.

At this stage the live MinIO volume archive was not an atomic DB/object
snapshot. The follow-up `2026-10-17-quiesced-backup.md` implements a coordinated
maintenance window and verifies it against native services with a live writer;
actual Docker and production-volume recovery remain release gates.

Evidence: 29 focused deployment tests pass. Native PostgreSQL 17 and MinIO
restore matched all 106 application tables, 10,000 synthetic orders and three
object digests; public/private policies, API readiness, customer history and
receipt, and the next order ID (10001) were verified. Only Docker transport
was emulated; source MinIO was stopped before copying. Owned services and
private fixtures were removed, shared MinIO was preserved. Eleven offline
map checks cover navigation, descriptions and widths 320/390/736. The map
state-reload check now waits for asynchronous persistence before reloading.
